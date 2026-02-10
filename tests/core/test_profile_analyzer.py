import pytest
from unittest.mock import MagicMock, patch
from core.models import SocialProfile, SocialPlatform, SocialPost, SocialAuthor
from core.profile_analyzer import ProfileAnalyzer, ProfileDossier, TechnicalLevel

@pytest.fixture
def mock_profile():
    return SocialProfile(
        username="test_user",
        platform=SocialPlatform.INSTAGRAM,
        bio="Senior Python Developer | AI Enthusiast",
        post_count=10,
        recent_posts=[
            SocialPost(
                id="1",
                platform=SocialPlatform.INSTAGRAM,
                author=SocialAuthor(username="test_user", platform=SocialPlatform.INSTAGRAM),
                content="Just refactored my codebase to use clean architecture patterns. #python #cleanarch",
                url="http://test.com/1"
            ),
            SocialPost(
                id="2",
                platform=SocialPlatform.INSTAGRAM,
                author=SocialAuthor(username="test_user", platform=SocialPlatform.INSTAGRAM),
                content="Exploring the new features of Pydantic V2. Validations are so much faster now!",
                url="http://test.com/2"
            )
        ]
    )

def test_analyze_profile_success(mock_profile):
    """Test that analyze_profile returns a valid dossier when LLM succeeds."""
    analyzer = ProfileAnalyzer()
    
    # Mock the agent run method
    mock_response = MagicMock()
    mock_response.content = ProfileDossier(
        summary="A senior developer focused on Python and best practices.",
        technical_level=TechnicalLevel.EXPERT,
        tone_preference="Professional",
        interests=["Python", "Software Architecture", "AI"],
        interaction_guidelines="Be technical and concise."
    )
    analyzer.agent.run = MagicMock(return_value=mock_response)
    
    dossier = analyzer.analyze_profile(mock_profile)
    
    assert dossier is not None
    assert dossier.technical_level == TechnicalLevel.EXPERT
    assert "Python" in dossier.interests
    assert analyzer.agent.run.called

def test_analyze_profile_error():
    """Test that analyze_profile handles errors gracefully."""
    analyzer = ProfileAnalyzer()
    analyzer.agent.run = MagicMock(side_effect=Exception("LLM Error"))
    
    dossier = analyzer.analyze_profile(SocialProfile(username="error_user", platform=SocialPlatform.INSTAGRAM))
    assert dossier is None
