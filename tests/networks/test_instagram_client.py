
import pytest
from unittest.mock import MagicMock, patch
from core.networks.instagram.client import InstagramClient
from core.models import SocialPost, SocialPlatform, SocialAuthor

@pytest.fixture
def mock_playwright():
    with patch("core.browser_manager.BrowserManager.get_playwright") as mock_get:
        mock_p = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()
        
        # Mock BrowserManager.get_playwright() returning the playwright instance
        mock_get.return_value = mock_p
        
        # Connect the chain
        mock_p.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page
        
        yield mock_p, mock_browser, mock_context, mock_page

def test_client_start(mock_playwright):
    """Test that client starts browser and loads state."""
    mock_p, mock_browser, mock_context, mock_page = mock_playwright
    
    client = InstagramClient()
    client.start()
    
    mock_p.chromium.launch.assert_called_once()
    # Depending on logic, new_context is called. 
    assert mock_browser.new_context.called

def test_get_hashtag_top_medias(mock_playwright):
    """Test fetching top medias from a hashtag."""
    mock_p, mock_browser, mock_context, mock_page = mock_playwright
    
    mock_page.content.return_value = "<html></html>"
    mock_page.query_selector_all.return_value = [] 
    
    client = InstagramClient()
    client.browser = mock_browser
    client.context = mock_context
    client.page = mock_page
    client._is_logged_in = True # Bypass login check
    
    posts = client.get_hashtag_top_medias("ai", amount=1)
    
    assert isinstance(posts, list)
    mock_page.goto.assert_called_with("https://www.instagram.com/explore/tags/ai/", timeout=30000)

def test_like_post_success(mock_playwright):
    """Test liking a post."""
    mock_p, mock_browser, mock_context, mock_page = mock_playwright
    
    client = InstagramClient()
    client.page = mock_page
    
    author = SocialAuthor(username="user", platform=SocialPlatform.INSTAGRAM)
    post = SocialPost(
        id="123",
        platform=SocialPlatform.INSTAGRAM,
        content="Test",
        url="http://instagr.am/p/123",
        author=author,
        media_urls=["http://example.com/img.jpg"]
    )
    
    client.like_post(post)
    
    # Should navigate to post url
    # We verify it called goto with the url
    args, _ = mock_page.goto.call_args
    assert "123" in args[0]
    
    # verify click was attempted
    assert mock_page.query_selector.called

def test_post_comment_success(mock_playwright):
    """Test posting a comment."""
    mock_p, mock_browser, mock_context, mock_page = mock_playwright
    
    client = InstagramClient()
    client.page = mock_page
    
    # Mock finding the textarea
    mock_textarea = MagicMock()
    mock_page.query_selector.return_value = mock_textarea
    
    author = SocialAuthor(username="user", platform=SocialPlatform.INSTAGRAM)
    post = SocialPost(
        id="123",
        platform=SocialPlatform.INSTAGRAM,
        content="Test",
        url="http://instagr.am/p/123",
        author=author
    )
    
    client.post_comment(post, "Great post!")
    
    args, _ = mock_page.goto.call_args
    assert "123" in args[0]
    
    # Check that it typed the comment
    assert mock_textarea.type.called or mock_textarea.fill.called
