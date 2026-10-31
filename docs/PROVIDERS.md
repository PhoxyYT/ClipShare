# Hosting integration status — 31 October 2026

Catbox's historically published API is `POST https://catbox.moe/user/api.php`
with multipart fields `reqtype=fileupload` and `fileToUpload`. Anonymous uploads
have historically had a 200 MB limit and returned a plain-text HTTPS URL at
`files.catbox.moe`. The implementation uses this protocol, imposes a conservative
200,000,000-byte cap, streams the body, validates the response host, and avoids
sending the original filename. No account credentials are requested or stored.

Primary sources to check before release/use:

- https://catbox.moe/tools.php — API documentation
- https://catbox.moe/faq.php — limits, availability, retention
- https://catbox.moe/legal.php — allowed content and terms

The environment proxy denied access to Catbox (HTTP CONNECT 403). Consequently
**current terms, current limits, geographic/service restrictions, allowed media
types, retention, and live MP4 browser playback could not be verified**. There is
no claim of provider endorsement, guaranteed permanence, or successful live upload.
The integration is experimental and discloses this before sending a file.

The HTTP integration test uses a local server, checks the actual multipart body,
and returns a mock URL. No test fixture has been published to an external service.
Cancellation stops streaming; a provider may already have received a file, and
cancellation cannot promise server-side deletion. A blocked socket can take up to
the 30-second read timeout to return. Retry is an explicit click, avoiding duplicate
automatic uploads. Upload progress measures bytes sent, not server processing.

Other candidates considered, without current-policy verification: Litterbox is
intended for expiring files and conflicts with the requested retention preference;
transfer.sh deployments have varying availability, limits, and expiration rules;
Gofile account/token and retention behavior needs current documentation. None is
integrated or presented as a verified suitable alternative. YouTube is excluded.

`HostingProvider` is the extension interface. Add a provider only after verifying
its actual API and automation/content policies. Native browser playback depends
on codec and the browser: H.264/AAC MP4 is the general compatibility choice;
uploading an original MKV or multitrack file preserves it but does not guarantee
that browsers will play all its streams.
