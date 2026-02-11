import unittest
from unittest.mock import MagicMock, patch
from core.networks.devto.client import DevToClient
from core.models import SocialPost, SocialPlatform, SocialAuthor

class TestDevToClient(unittest.TestCase):
    def setUp(self):
        self.client = DevToClient()
        self.client.api_key = "test_key"

    @patch("core.networks.devto.client.requests.get")
    def test_login_success(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"username": "testuser"}
        
        self.assertTrue(self.client.login())

    @patch("core.networks.devto.client.requests.get")
    def test_login_failure(self, mock_get):
        mock_get.return_value.status_code = 401
        self.assertFalse(self.client.login())

    @patch("core.networks.devto.client.requests.get")
    def test_get_post_details(self, mock_get):
        # Mock article response
        article_data = {
            "id": 123,
            "user": {"username": "author", "user_id": 1, "name": "Author Name"},
            "body_markdown": "Test content",
            "url": "https://dev.to/author/test",
            "public_reactions_count": 10,
            "comments_count": 5
        }
        
        # Mock comments response
        comments_data = [
            {
                "id_code": "abc",
                "user": {"username": "commenter", "user_id": 2},
                "body_html": "<p>Great post!</p>"
            }
        ]

        # Configure mock to return different values for different calls
        def side_effect(url, headers, params=None):
            if "/articles/123" in url:
                mock = MagicMock()
                mock.status_code = 200
                mock.json.return_value = article_data
                return mock
            elif "/comments" in url:
                mock = MagicMock()
                mock.status_code = 200
                mock.json.return_value = comments_data
                return mock
            return MagicMock(status_code=404)

        mock_get.side_effect = side_effect

        post = self.client.get_post_details("123")
        
        self.assertIsNotNone(post)
        self.assertEqual(post.id, "123")
        self.assertEqual(post.author.username, "author")
        self.assertEqual(len(post.comments), 1)
        self.assertEqual(post.comments[0].text, "Great post!")

    @patch("core.networks.devto.client.requests.post")
    def test_post_comment(self, mock_post):
        mock_post.return_value.status_code = 201
        
        post = SocialPost(
            id="123",
            platform=SocialPlatform.DEVTO,
            author=SocialAuthor(username="author", platform=SocialPlatform.DEVTO),
            content="Content",
            url="url"
        )
        
        success = self.client.post_comment(post, "Great article!")
        self.assertTrue(success)
        
        # Verify payload
        args, kwargs = mock_post.call_args
        self.assertEqual(kwargs['json']['comment']['body_markdown'], "Great article!")
        self.assertEqual(kwargs['json']['comment']['commentable_id'], 123)

if __name__ == '__main__':
    unittest.main()
