"""
Tests for chat session processing functions.
"""
import pytest
import json

from services.lecture_utils import (
    preprocess_chat_session,
    extract_links_from_chat,
    format_chat_links_for_prompt,
)


class TestPreprocessChatSession:
    """Tests for preprocess_chat_session function."""
    
    def test_returns_valid_json(self, sample_chat_raw):
        """Output should be valid JSON."""
        result = preprocess_chat_session(sample_chat_raw)
        messages = json.loads(result)
        assert isinstance(messages, list)
    
    def test_message_structure(self, sample_chat_raw):
        """Each message should have name, time, content keys."""
        result = preprocess_chat_session(sample_chat_raw)
        messages = json.loads(result)
        
        for msg in messages:
            assert "name" in msg
            assert "time" in msg
            assert "content" in msg
    
    def test_filters_junk_lines(self, sample_chat_raw):
        """Should filter out Collapse All, emoji reactions, pure numbers."""
        result = preprocess_chat_session(sample_chat_raw)
        messages = json.loads(result)
        
        # Check that "Collapse All" is not in any message content
        for msg in messages:
            assert "Collapse All" not in msg["content"]
    
    def test_keeps_messages_with_links(self, sample_chat_raw):
        """Messages containing URLs should be kept regardless of length."""
        result = preprocess_chat_session(sample_chat_raw)
        messages = json.loads(result)
        
        # Should have at least one message with a link
        has_link = any("http" in msg["content"] for msg in messages)
        assert has_link
    
    def test_keeps_long_messages(self, sample_chat_raw):
        """Messages with >= 6 words should be kept."""
        result = preprocess_chat_session(sample_chat_raw)
        messages = json.loads(result)
        
        # The CNN layers message should be kept (multi-line, informative)
        has_cnn_content = any("CNN" in msg["content"] or "layer" in msg["content"].lower() 
                             for msg in messages)
        assert has_cnn_content
    
    def test_keeps_code_blocks(self, sample_chat_raw):
        """Messages with >= 3 lines (code blocks) should be kept."""
        result = preprocess_chat_session(sample_chat_raw)
        messages = json.loads(result)
        
        # The code block message should be kept
        has_code = any("import" in msg["content"] or "class" in msg["content"] 
                      for msg in messages)
        assert has_code
    
    def test_filters_short_messages(self, sample_chat_raw):
        """Short messages like 'ok', emoji should be filtered."""
        result = preprocess_chat_session(sample_chat_raw)
        messages = json.loads(result)
        
        # "ok" as standalone should not appear
        contents = [msg["content"].strip().lower() for msg in messages]
        assert "ok" not in contents
    
    def test_empty_input(self):
        """Empty input should return empty JSON array."""
        result = preprocess_chat_session("")
        messages = json.loads(result)
        assert messages == []
    
    def test_preserves_newlines_in_content(self, sample_chat_raw):
        """Content with multiple lines should preserve newlines."""
        result = preprocess_chat_session(sample_chat_raw)
        messages = json.loads(result)
        
        # Multi-line messages should have \n in content
        multi_line_msgs = [msg for msg in messages if "\n" in msg["content"]]
        assert len(multi_line_msgs) > 0


class TestExtractLinksFromChat:
    """Tests for extract_links_from_chat function."""
    
    def test_extracts_urls(self):
        """Should extract URLs from chat content."""
        chat_json = json.dumps([
            {"name": "User", "time": "10:00", "content": "Check https://example.com for info"}
        ])
        links = extract_links_from_chat(chat_json)
        
        assert len(links) == 1
        assert "<https://example.com>" in links[0]
    
    def test_excludes_kahoot_links(self):
        """Should exclude Kahoot links."""
        chat_json = json.dumps([
            {"name": "User", "time": "10:00", "content": "Join https://kahoot.it/challenge/123"}
        ])
        links = extract_links_from_chat(chat_json)
        
        assert len(links) == 0
    
    def test_excludes_discord_links(self):
        """Should exclude Discord links."""
        chat_json = json.dumps([
            {"name": "User", "time": "10:00", "content": "https://discord.gg/invite123"}
        ])
        links = extract_links_from_chat(chat_json)
        
        assert len(links) == 0
    
    def test_deduplicates_links(self):
        """Should remove duplicate URLs."""
        chat_json = json.dumps([
            {"name": "User1", "time": "10:00", "content": "Check https://example.com"},
            {"name": "User2", "time": "10:01", "content": "Same link https://example.com"}
        ])
        links = extract_links_from_chat(chat_json)
        
        assert len(links) == 1
    
    def test_multiple_links(self):
        """Should extract multiple different links."""
        chat_json = json.dumps([
            {"name": "User", "time": "10:00", "content": "Links: https://example.com and https://docs.google.com/doc"}
        ])
        links = extract_links_from_chat(chat_json)
        
        assert len(links) == 2
    
    def test_empty_chat(self):
        """Empty chat should return empty list."""
        links = extract_links_from_chat("[]")
        assert links == []


class TestFormatChatLinksForPrompt:
    """Tests for format_chat_links_for_prompt function."""
    
    def test_formats_links(self):
        """Should format links with header."""
        links = ["<https://example.com>", "<https://docs.google.com>"]
        result = format_chat_links_for_prompt(links)
        
        assert "Links từ chat" in result or "chat" in result.lower()
        assert "<https://example.com>" in result
    
    def test_empty_links(self):
        """Empty list should return empty string."""
        result = format_chat_links_for_prompt([])
        assert result == ""
    
    def test_single_link(self):
        """Single link should format correctly."""
        links = ["<https://example.com>"]
        result = format_chat_links_for_prompt(links)
        
        assert len(result) > 0
        assert "<https://example.com>" in result
