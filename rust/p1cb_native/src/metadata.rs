//! Known 1C metadata type UUIDs and English class folder names for CF layout.
//! Port of `parse_1c_build.metadata_types`.

use once_cell::sync::Lazy;
use std::collections::HashMap;

/// type UUID (lowercase) -> (folder name under objects/, root_bsl_prefix or None)
pub static METADATA_TYPES: Lazy<HashMap<&'static str, (&'static str, Option<&'static str>)>> =
    Lazy::new(|| {
        let mut m = HashMap::new();
        // Root-level specials (common)
        m.insert(
            "0fe48980-252d-11d6-a3c7-0050bae0a776",
            ("CommonModules", Some("9_")),
        );
        m.insert(
            "07ee8426-87f1-11d5-b99c-0050bae0a95d",
            ("CommonForms", Some("1_")),
        );
        m.insert(
            "2f1a5187-fb0e-4b05-9489-dc5dd6412348",
            ("CommonCommands", Some("2_")),
        );
        // Objects with Class/Name layout under objects/
        m.insert("cf4abea6-37b2-11d4-940f-008048da11f9", ("Catalogs", None));
        m.insert("061d872a-5787-460e-95ac-ed74ea3a3e84", ("Documents", None));
        m.insert("0195e80c-b157-11d4-9435-004095e12fc7", ("Constants", None));
        m.insert("f6a80749-5ad7-400b-8519-39dc5dff2542", ("Enums", None));
        m.insert(
            "4612bd75-71b7-4a5c-8cc5-2b0b65f9fa0d",
            ("DocumentJournals", None),
        );
        m.insert(
            "13134201-f60b-11d5-a3c7-0050bae0a776",
            ("InformationRegisters", None),
        );
        m.insert(
            "b64d9a40-1642-11d6-a3c7-0050bae0a776",
            ("AccumulationRegisters", None),
        );
        m.insert(
            "2deed9b8-0056-4ffe-a473-c20a6c32a0bc",
            ("AccountingRegisters", None),
        );
        m.insert(
            "f2de87a8-64e5-45eb-a22d-b3aedab050e7",
            ("CalculationRegisters", None),
        );
        m.insert(
            "bf845118-327b-4682-b5c6-285d2a0eb296",
            ("DataProcessors", None),
        );
        m.insert("631b75a0-29e2-11d6-a3c7-0050bae0a776", ("Reports", None));
        m.insert(
            "fcd3404e-1523-48ce-9bc0-ecdb822684a1",
            ("BusinessProcesses", None),
        );
        m.insert("3e63355c-1378-4953-be9b-1deb5fb6bec5", ("Tasks", None));
        m.insert(
            "857c4a91-e5f4-4fac-86ec-787626f1c108",
            ("ExchangePlans", None),
        );
        m.insert(
            "3e7bfcc0-067d-11d6-a3c7-0050bae0a776",
            ("FilterCriteria", None),
        );
        m.insert(
            "46b4cd97-fd13-4eaa-aba2-3bddd7699218",
            ("SettingsStorages", None),
        );
        m.insert("8657032e-7740-4e1d-a3ba-5dd6e8afb78f", ("WebServices", None));
        m.insert(
            "0fffc09c-8f4c-47cc-b41c-8d5c5a221d79",
            ("HTTPServices", None),
        );
        m.insert(
            "bf3420b0-f6f9-41a0-b83a-fe9d4ab0b65d",
            ("IntegrationServices", None),
        );
        m.insert("6e6dc072-b7ac-41e7-8f88-278d25b6da2a", ("Bots", None));
        m.insert(
            "82a1b659-b220-4d94-a9bd-14d757b95a48",
            ("ChartsOfCharacteristicTypes", None),
        );
        m.insert(
            "238e7e88-3c5f-48b2-8a3b-81ebbecb20ed",
            ("ChartsOfAccounts", None),
        );
        m.insert(
            "30b100d6-b29f-47ac-aec7-cb8ca8a54767",
            ("ChartsOfCalculationTypes", None),
        );
        m.insert(
            "5274d9fc-9c3a-4a71-8f5e-a0db8ab23de5",
            ("ExternalDataSources", None),
        );
        // Structural / usually no BSL at object root (still Class/Name for roundtrip)
        m.insert("09736b02-9cac-4e3f-b4f7-d3e9576ab948", ("Roles", None));
        m.insert("37f2fa9a-b276-11d4-9435-004095e12fc7", ("Subsystems", None));
        m.insert("9cd510ce-abfc-11d4-9434-004095e12fc7", ("Languages", None));
        m.insert(
            "0c89c792-16c3-11d5-b96b-0050bae0a95d",
            ("CommonTemplates", None),
        );
        m.insert(
            "7dcd43d9-aca5-4926-b549-1842e6a4e8cf",
            ("CommonPictures", None),
        );
        m.insert(
            "11bdaf85-d5ad-4d91-bb24-aa0eee139052",
            ("ScheduledJobs", None),
        );
        m.insert(
            "4e828da6-0f44-4b5b-b1c0-a2b3cfe7bdcc",
            ("EventSubscriptions", None),
        );
        m.insert(
            "24c43748-c938-45d0-8d14-01424a72b11e",
            ("SessionParameters", None),
        );
        m.insert(
            "15794563-ccec-41f6-a83c-ec5f7b9a5bc1",
            ("CommonAttributes", None),
        );
        m.insert(
            "af547940-3268-434f-a3e7-e47d6d2638c3",
            ("FunctionalOptions", None),
        );
        m.insert(
            "30d554db-541e-4f62-8970-a1c6dcfeb2bc",
            ("FunctionalOptionsParameters", None),
        );
        m.insert(
            "1c57eabe-7349-44b3-b1de-ebfeab67b47d",
            ("CommandGroups", None),
        );
        m.insert(
            "c045099e-13b9-4fb6-9d50-fca00202971e",
            ("DefinedTypes", None),
        );
        m.insert(
            "cc9df798-7c94-4616-97d2-7aa0b7bc515e",
            ("XDTOPackages", None),
        );
        m.insert("d26096fb-7a5d-4df9-af63-47d04771fa9b", ("WSReferences", None));
        m.insert("39bddf6a-0c3c-452b-921c-d99cfa1c2f1b", ("Interfaces", None));
        m.insert("3e5404af-6ef8-4c73-ad11-91bd2dfac4c8", ("Styles", None));
        m.insert("58848766-36ea-4076-8800-e91eb49590d7", ("StyleItems", None));
        m.insert("bc587f20-35d9-11d6-a3c7-0050bae0a776", ("Sequences", None));
        m.insert(
            "36a8e346-9aaa-4af9-bdbd-83be3c177977",
            ("DocumentNumerators", None),
        );
        m
    });

pub const CONFIGURATION_TYPE_UUID: &str = "9cd510cd-abfc-11d4-9434-004095e12fc7";

/// Secondary container index under configuration identity → config module role name
pub static CONFIG_MODULE_SLOTS: Lazy<HashMap<u32, &'static str>> = Lazy::new(|| {
    let mut m = HashMap::new();
    m.insert(5, "УправляемоеПриложение");
    m.insert(6, "ОбычноеПриложение");
    m.insert(7, "Сеанс");
    m.insert(8, "ВнешнееСоединение");
    m
});
