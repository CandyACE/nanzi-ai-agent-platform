from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_metadata_dataset_pages_use_svg_dataset_icons() -> None:
    for relative_path in (
        "frontend/src/views/MetadataDatasets.vue",
        "frontend/src/views/MetadataTables.vue",
    ):
        source = _read(relative_path)
        assert "CircleStackIcon" in source
        assert "getDatasetEmoji" not in source
        for emoji in ("📊", "📈", "💿", "🗄️", "📂"):
            assert emoji not in source


def test_metadata_database_import_uses_svg_icons() -> None:
    source = _read("frontend/src/components/metadata/DatabaseImportModal.vue")

    assert "CircleStackIcon" in source
    assert "CpuChipIcon" in source
    for emoji in ("🐬", "🐘", "🧊", "🤖", "🗄️"):
        assert emoji not in source


def test_metadata_relationship_and_metric_ui_use_svg_icons() -> None:
    relationship = _read("frontend/src/components/metadata/RelationshipList.vue")
    metric = _read("frontend/src/components/metadata/MetricList.vue")

    for icon in ("CircleStackIcon", "KeyIcon", "LinkIcon", "LightBulbIcon"):
        assert icon in relationship
    assert "SparklesIcon" in metric
    assert "✨ 智能发现指标" not in metric


def test_message_action_bar_does_not_clip_desktop_menus() -> None:
    source = _read("frontend/src/views/EmbedChat.vue")
    assert "overflow-x-auto sm:overflow-x-visible" in source


def test_message_action_menu_uses_svg_for_trace_icon() -> None:
    source = _read("frontend/src/components/chat/MessageActionMenus.vue")
    assert "BoltIcon" in source
    assert "⚡ 查看执行链路" not in source
