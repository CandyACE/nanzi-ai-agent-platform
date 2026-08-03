from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_embed_chat_agent_messages_use_the_nanzi_agent_avatar_asset():
    source = (ROOT / "frontend/src/views/EmbedChat.vue").read_text(encoding="utf-8")
    bundled_avatar = ROOT / "frontend/src/assets/nanzi-agent-avatar.svg"
    brand_avatar = ROOT / "docs/brand/nanzi-agent-avatar.svg"

    assert 'import agentAvatarUrl from "@/assets/nanzi-agent-avatar.svg";' in source
    assert "'/branding/nanzi-agent-avatar.svg'" not in source
    assert ':src="agentAvatarUrl"' in source
    assert 'alt="NanZi AI agent"' in source
    assert bundled_avatar.is_file()
    assert bundled_avatar.read_bytes() == brand_avatar.read_bytes()
