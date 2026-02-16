# Fixing Twitter API Permissions

If you encounter the error:
> `403 Forbidden: Your client app is not configured with the appropriate oauth1 app permissions for this endpoint`

This means your Twitter App has "Read Only" permissions (default), but you are trying to post tweets (which requires "Read and Write").

## Steps to fix:

1. Go to the [Twitter Developer Portal](https://developer.twitter.com/en/portal/dashboard).
2. Select your Project / App.
3. Find **User authentication settings** and click **Edit**.
4. Change **App permissions** from **Read** to **Read and Write** (or "Read and Write and Direct Message").
5. Save the changes.
6. **IMPORTANT:** Go to the **Keys and tokens** tab.
7. Under **Authentication Tokens**, find your existing **Access Token and Secret** and click **Regenerate**.
   *(Old tokens are tied to the old "Read Only" permission scope and will **not** work).*
8. Copy the **NEW** Access Token and Secret.
9. Update your `.env` file with these new values.

After updating `.env`, run the test script again:
```bash
./venv/bin/python scripts/test_twitter_api.py
```
