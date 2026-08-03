//! BSL extract helpers — port of `parse_1c_build.bsl` pieces used by CF layout.

use once_cell::sync::Lazy;
use regex::Regex;
use std::fs;
use std::io;
use std::path::{Path, PathBuf};

pub const BSL_PLACEHOLDER: &str = "<BSL_MODULE_PLACEHOLDER>";
pub const MOXCEL_FORM_PREFIX: &str = "MOXCEL";
pub const BSL_RENAMES_FILENAME: &str = "bsl_renames.txt";
pub const BIN_DIRNAME: &str = "bin";
pub const META_DIRNAME: &str = "meta";
pub const OBJECTS_DIRNAME: &str = "objects";
pub const RENAMES_ARROW: &str = " --> ";
/// Match Python text-mode `open(..., "w")` newline translation on the host OS.
#[cfg(windows)]
pub const LINE_ENDING: &str = "\r\n";
#[cfg(not(windows))]
pub const LINE_ENDING: &str = "\n";
pub const BSL_PREFIX_OBJECT: &str = "0_";
pub const BSL_PREFIX_FORM: &str = "1_";
pub const BSL_PREFIX_COMMAND: &str = "2_";
#[allow(dead_code)]
pub const BSL_PREFIX_COMMON_MODULE: &str = "9_";

static RE_FORM_TUPLE: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r#"(\{\r?\n?)|("(?:""|[^"]*)*")|([^},\{]+)|(,\r?\n?)|(\}\r?\n?)"#).unwrap()
});

static RE_MANAGED_FORM_FILE: Lazy<Regex> = Lazy::new(|| {
    Regex::new(
        r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\.0$",
    )
    .unwrap()
});

static RE_FORM_DESC_NAME: Lazy<Regex> =
    Lazy::new(|| Regex::new(r#"\{1,0,[0-9a-fA-F-]{36}\},\s*"([^"]+)""#).unwrap());

const UTF8_BOM: &[u8] = &[0xEF, 0xBB, 0xBF];

/// Read file as UTF-8; return (content, has_bom) or None on error.
pub fn read_file_content(path: &Path) -> Option<(String, bool)> {
    let raw = fs::read(path).ok()?;
    let has_bom = raw.starts_with(UTF8_BOM);
    let content = decode_utf8_sig(&raw).ok()?;
    Some((content, has_bom))
}

/// Decode like Python `bytes.decode("utf-8-sig")`: strip leading EF BB BF then UTF-8.
pub fn decode_utf8_sig(raw: &[u8]) -> Result<String, std::str::Utf8Error> {
    let body = if raw.starts_with(UTF8_BOM) {
        &raw[3..]
    } else {
        raw
    };
    std::str::from_utf8(body).map(|s| s.to_owned())
}

/// Write text without newline translation; optionally prepend UTF-8 BOM.
pub fn write_text_bytes(path: &Path, text: &str, with_bom: bool) -> io::Result<()> {
    let mut bytes = Vec::with_capacity(text.len() + 3);
    if with_bom {
        bytes.extend_from_slice(UTF8_BOM);
    }
    bytes.extend_from_slice(text.as_bytes());
    fs::write(path, bytes)
}

pub fn is_managed_form_file(path: &Path) -> bool {
    path.file_name()
        .and_then(|n| n.to_str())
        .map(|name| RE_MANAGED_FORM_FILE.is_match(name))
        .unwrap_or(false)
}

/// Read description file (UUID) and return form/object name, or None.
pub fn get_form_or_object_name(root: &Path, uuid_dot0_name: &str) -> Option<String> {
    if !uuid_dot0_name.ends_with(".0") {
        return None;
    }
    let desc_name = &uuid_dot0_name[..uuid_dot0_name.len() - 2];
    let desc_path = root.join(desc_name);
    let (content, _) = read_file_content(&desc_path)?;
    RE_FORM_DESC_NAME
        .captures(&content)
        .map(|c| c.get(1).unwrap().as_str().to_owned())
}

/// Find BSL module as (element_index+1)-th element of root tuple.
/// Returns (body, replace_start, replace_end) with outer quotes stripped and `""` → `"`.
///
/// Offsets are **byte** indices into `content` (Rust `&str` slicing).
pub fn find_form_module_by_tuple(
    content: &str,
    element_index: usize,
) -> Option<(String, usize, usize)> {
    let mut line_no: usize = 1;
    let mut index_parent = String::new();
    let mut current_index: usize = 0;
    let mut start_line: usize = 0;
    let mut _end_line: usize = 0;
    let mut value: Option<String> = None;
    let mut value_span: Option<(usize, usize)> = None;

    for caps in RE_FORM_TUPLE.captures_iter(content) {
        if index_parent == "0" && current_index == element_index {
            start_line = line_no;
        }

        if caps.get(4).is_some() {
            current_index += 1;
            line_no += caps.get(4).unwrap().as_str().matches('\n').count();
        } else if caps.get(1).is_some() {
            if index_parent.is_empty() {
                index_parent = current_index.to_string();
            } else {
                index_parent = format!("{}:{}", index_parent, current_index);
            }
            current_index = 0;
            line_no += caps.get(1).unwrap().as_str().matches('\n').count();
        } else if caps.get(5).is_some() {
            if !index_parent.is_empty() {
                let mut parts: Vec<&str> = index_parent.split(':').collect();
                current_index = parts.pop().unwrap().parse().unwrap_or(0);
                index_parent = parts.join(":");
            }
            line_no += caps.get(5).unwrap().as_str().matches('\n').count();
        } else if let Some(g3) = caps.get(3) {
            value = Some(g3.as_str().to_owned());
            let s = g3.as_str();
            line_no += s.matches('\n').count() + s.matches('\r').count();
        } else if let Some(g2) = caps.get(2) {
            value = Some(g2.as_str().to_owned());
            value_span = Some((g2.start(), g2.end()));
            line_no += g2.as_str().matches('\n').count();
            if start_line != 0 {
                _end_line = line_no;
                break;
            }
        }
    }

    let raw = value?;
    let (start, end) = value_span?;
    if start_line == 0 {
        return None;
    }

    // Strip outer quotes and unescape "" → "
    if raw.len() < 2 {
        return None;
    }
    let body = raw[1..raw.len() - 1].replace("\"\"", "\"");
    Some((body, start, end))
}

/// Like [`find_form_module_by_tuple`], but offsets are Python/`str` character indices.
pub fn find_form_module_by_tuple_char_offsets(
    content: &str,
    element_index: usize,
) -> Option<(String, usize, usize)> {
    let (body, byte_start, byte_end) = find_form_module_by_tuple(content, element_index)?;
    let char_start = content[..byte_start].chars().count();
    let char_end = char_start + content[byte_start..byte_end].chars().count();
    Some((body, char_start, char_end))
}

fn looks_like_tuple_module(content: &str) -> bool {
    let stripped = content.trim_start_matches('\u{feff}').trim_start();
    if !stripped.starts_with('{') {
        return false;
    }
    if stripped.starts_with("<?xml") || stripped.starts_with('<') {
        return false;
    }
    true
}

fn extract_plain_module(
    path: &Path,
    content: &str,
    with_bom: bool,
    bsl_path: Option<&Path>,
) -> io::Result<bool> {
    let dest: PathBuf = match bsl_path {
        Some(p) => p.to_path_buf(),
        None => {
            let name = path.file_name().unwrap().to_string_lossy();
            path.with_file_name(format!("{}.bsl", name))
        }
    };
    write_text_bytes(&dest, content, with_bom)?;
    write_text_bytes(path, BSL_PLACEHOLDER, with_bom)?;
    Ok(true)
}

fn extract_managed_form(
    path: &Path,
    content: &str,
    with_bom: bool,
    bsl_path: Option<&Path>,
) -> io::Result<bool> {
    if content.starts_with(MOXCEL_FORM_PREFIX) {
        return Ok(false);
    }
    if !looks_like_tuple_module(content) {
        return Ok(false);
    }

    let Some((code, replace_start, replace_end)) = find_form_module_by_tuple(content, 2) else {
        return Ok(false);
    };
    if code.trim() == BSL_PLACEHOLDER {
        return Ok(false);
    }

    let dest: PathBuf = match bsl_path {
        Some(p) => p.to_path_buf(),
        None => {
            let name = path.file_name().unwrap().to_string_lossy();
            path.with_file_name(format!("{}.bsl", name))
        }
    };
    write_text_bytes(&dest, &code, with_bom)?;

    let placeholder_in_file = format!("\"{}\"", BSL_PLACEHOLDER);
    let mut new_content = String::with_capacity(content.len());
    new_content.push_str(&content[..replace_start]);
    new_content.push_str(&placeholder_in_file);
    new_content.push_str(&content[replace_end..]);
    write_text_bytes(path, &new_content, with_bom)?;
    Ok(true)
}

/// Extract BSL code embedded in `path` into a companion .bsl file.
pub fn split_file(path: &Path, bsl_dest_path: Option<&Path>) -> io::Result<bool> {
    let Some((content, has_bom)) = read_file_content(path) else {
        return Ok(false);
    };
    if content.trim() == BSL_PLACEHOLDER {
        return Ok(false);
    }

    let name = path.file_name().and_then(|n| n.to_str()).unwrap_or("");
    if name == "module" || name == "text" {
        let stripped = content.trim();
        if !(stripped.starts_with('{') && stripped.contains('}')) {
            return extract_plain_module(path, &content, has_bom, bsl_dest_path);
        }
    }

    if is_managed_form_file(path) {
        return extract_managed_form(path, &content, has_bom, bsl_dest_path);
    }

    Ok(false)
}

/// Write meta/bsl_renames.txt from (bsl_filename, companion_rel) list.
pub fn write_bsl_renames_file(root: &Path, renames_entries: &[(String, String)]) -> io::Result<()> {
    if renames_entries.is_empty() {
        return Ok(());
    }
    let meta_path = root.join(META_DIRNAME);
    fs::create_dir_all(&meta_path)?;
    let path = meta_path.join(BSL_RENAMES_FILENAME);
    let mut out = String::new();
    for (bsl_name, companion) in renames_entries {
        out.push_str(bsl_name);
        out.push_str(RENAMES_ARROW);
        out.push_str(companion);
        out.push_str(crate::bsl::LINE_ENDING);
    }
    // Python open("w", encoding="utf-8") — no BOM
    fs::write(path, out.as_bytes())
}
