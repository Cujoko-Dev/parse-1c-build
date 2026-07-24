"""Known 1C metadata type UUIDs and Russian class folder names for CF layout."""

from __future__ import annotations

# type UUID (lowercase) -> (folder name under *_cf_src, root_bsl_prefix or None)
# root_bsl_prefix: if set, object modules go to CF root with that prefix (not Class/Name/).
# None means object mini-layout under Class/Name/.

METADATA_TYPES: dict[str, tuple[str, str | None]] = {
    # Root-level specials (common)
    "0fe48980-252d-11d6-a3c7-0050bae0a776": ("ОбщиеМодули", "9_"),
    "07ee8426-87f1-11d5-b99c-0050bae0a95d": ("ОбщиеФормы", "1_"),
    "2f1a5187-fb0e-4b05-9489-dc5dd6412348": ("ОбщиеКоманды", "2_"),
    # Objects with Class/Name layout
    "cf4abea6-37b2-11d4-940f-008048da11f9": ("Справочники", None),
    "061d872a-5787-460e-95ac-ed74ea3a3e84": ("Документы", None),
    "0195e80c-b157-11d4-9435-004095e12fc7": ("Константы", None),
    "f6a80749-5ad7-400b-8519-39dc5dff2542": ("Перечисления", None),
    "4612bd75-71b7-4a5c-8cc5-2b0b65f9fa0d": ("ЖурналыДокументов", None),
    "13134201-f60b-11d5-a3c7-0050bae0a776": ("РегистрыСведений", None),
    "b64d9a40-1642-11d6-a3c7-0050bae0a776": ("РегистрыНакопления", None),
    "2deed9b8-0056-4ffe-a473-c20a6c32a0bc": ("РегистрыБухгалтерии", None),
    "f2de87a8-64e5-45eb-a22d-b3aedab050e7": ("РегистрыРасчета", None),
    "bf845118-327b-4682-b5c6-285d2a0eb296": ("Обработки", None),
    "631b75a0-29e2-11d6-a3c7-0050bae0a776": ("Отчеты", None),
    "fcd3404e-1523-48ce-9bc0-ecdb822684a1": ("БизнесПроцессы", None),
    "3e63355c-1378-4953-be9b-1deb5fb6bec5": ("Задачи", None),
    "857c4a91-e5f4-4fac-86ec-787626f1c108": ("ПланыОбмена", None),
    "3e7bfcc0-067d-11d6-a3c7-0050bae0a776": ("КритерииОтбора", None),
    "46b4cd97-fd13-4eaa-aba2-3bddd7699218": ("ХранилищаНастроек", None),
    "8657032e-7740-4e1d-a3ba-5dd6e8afb78f": ("WebСервисы", None),
    "0fffc09c-8f4c-47cc-b41c-8d5c5a221d79": ("HTTPСервисы", None),
    "bf3420b0-f6f9-41a0-b83a-fe9d4ab0b65d": ("СервисыИнтеграции", None),
    "6e6dc072-b7ac-41e7-8f88-278d25b6da2a": ("Боты", None),
    "82a1b659-b220-4d94-a9bd-14d757b95a48": ("ПланыВидовХарактеристик", None),
    "238e7e88-3c5f-48b2-8a3b-81ebbecb20ed": ("ПланыСчетов", None),
    "30b100d6-b29f-47ac-aec7-cb8ca8a54767": ("ПланыВидовРасчета", None),
    "5274d9fc-9c3a-4a71-8f5e-a0db8ab23de5": ("ВнешниеИсточникиДанных", None),
    # Structural / usually no BSL at object root (still Class/Name for roundtrip)
    "09736b02-9cac-4e3f-b4f7-d3e9576ab948": ("Роли", None),
    "37f2fa9a-b276-11d4-9435-004095e12fc7": ("Подсистемы", None),
    "9cd510ce-abfc-11d4-9434-004095e12fc7": ("Языки", None),
    "0c89c792-16c3-11d5-b96b-0050bae0a95d": ("ОбщиеМакеты", None),
    "7dcd43d9-aca5-4926-b549-1842e6a4e8cf": ("ОбщиеКартинки", None),
    "11bdaf85-d5ad-4d91-bb24-aa0eee139052": ("РегламентныеЗадания", None),
    "4e828da6-0f44-4b5b-b1c0-a2b3cfe7bdcc": ("ПодпискиНаСобытия", None),
    "24c43748-c938-45d0-8d14-01424a72b11e": ("ПараметрыСеанса", None),
    "15794563-ccec-41f6-a83c-ec5f7b9a5bc1": ("ОбщиеРеквизиты", None),
    "af547940-3268-434f-a3e7-e47d6d2638c3": ("ФункциональныеОпции", None),
    "30d554db-541e-4f62-8970-a1c6dcfeb2bc": ("ПараметрыФункциональныхОпций", None),
    "1c57eabe-7349-44b3-b1de-ebfeab67b47d": ("ГруппыКоманд", None),
    "c045099e-13b9-4fb6-9d50-fca00202971e": ("ОпределяемыеТипы", None),
    "cc9df798-7c94-4616-97d2-7aa0b7bc515e": ("ПакетыXDTO", None),
    "d26096fb-7a5d-4df9-af63-47d04771fa9b": ("WSСсылки", None),
    "39bddf6a-0c3c-452b-921c-d99cfa1c2f1b": ("Интерфейсы", None),
    "3e5404af-6ef8-4c73-ad11-91bd2dfac4c8": ("Стили", None),
    "58848766-36ea-4076-8800-e91eb49590d7": ("ЭлементыСтиля", None),
    "bc587f20-35d9-11d6-a3c7-0050bae0a776": ("Последовательности", None),
    "36a8e346-9aaa-4af9-bdbd-83be3c177977": ("Нумераторы", None),
}

CONFIGURATION_TYPE_UUID = "9cd510cd-abfc-11d4-9434-004095e12fc7"

# Secondary container index under configuration identity → config module role name
CONFIG_MODULE_SLOTS: dict[int, str] = {
    5: "УправляемоеПриложение",
    6: "ОбычноеПриложение",
    7: "Сеанс",
    8: "ВнешнееСоединение",
}
