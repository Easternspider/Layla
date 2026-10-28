# Codex account connection

In Settings → Providers, select **Connect Codex**. Before that, enable device-code login in ChatGPT: Settings → Security. Layla opens `https://auth.openai.com/codex/device` and shows the confirmation code. Approve it with the ChatGPT account that has the Codex subscription. Layla then loads the models that account can use. No password and no API key are entered into Layla.

This is a ChatGPT subscription token. It is sent only to `https://chatgpt.com/backend-api/codex`, never to `api.openai.com`. An `sk-` key is a different credential and still belongs in a normal provider profile. Model discovery calls `GET /models?client_version=<Codex CLI version>`; ChatGPT rejects the list without that parameter. `LAYLA_CODEX_CLIENT_VERSION` overrides the default.

If ChatGPT has device login turned off, the start request fails and tells you to enable it. If model discovery fails after a successful login, the encrypted connection stays saved. Use **Загрузить модели** on that provider to retry. Connect Codex again to replace the account. Delete the provider to remove the stored credentials.

Run the normal database migration (`alembic upgrade head`) when deploying. Revision `0032_codex_login` stores the pending device grant so polling survives restarts. The device id, access token and refresh token are encrypted with the existing Layla secret and are not returned to the browser.

`LAYLA_CODEX_CLIENT_ID` can override the public Codex CLI client id. Automated tests mock ChatGPT. A real account still has to approve a code once after deployment.
