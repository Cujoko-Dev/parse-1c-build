//! Optional Rust/PyO3 acceleration for parse-1c-build CF layout.

mod bsl;
mod cf_layout;
mod metadata;

use pyo3::prelude::*;
use pyo3::exceptions::PyException;
use std::collections::HashMap;

/// Organize flat v8unpack CF dump in place; return phase timings (seconds).
#[pyfunction]
fn organize_configuration_dir(dump_dir: &str) -> PyResult<HashMap<String, f64>> {
    cf_layout::organize_configuration_dir(dump_dir)
        .map_err(|e| PyException::new_err(e))
}

/// Find BSL module string in a 1C tuple form file.
/// Returns (body, replace_start, replace_end) with quotes stripped and `""` → `"`.
/// Offsets are Python character indices (compatible with `str` slicing).
#[pyfunction]
#[pyo3(signature = (content, element_index=2))]
fn find_form_module_by_tuple(
    content: &str,
    element_index: usize,
) -> Option<(String, usize, usize)> {
    bsl::find_form_module_by_tuple_char_offsets(content, element_index)
}

#[pymodule]
fn p1cb_native(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(organize_configuration_dir, m)?)?;
    m.add_function(wrap_pyfunction!(find_form_module_by_tuple, m)?)?;
    Ok(())
}
