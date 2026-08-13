# Test Credentials — Veridian

## Insights Dashboard (OTP-only login, whitelist-restricted)
Login is passwordless. Enter a whitelisted email, receive a real 6-digit OTP via email, then verify.

Whitelisted authorized emails (only these can log in):
- aman7339811186@gmail.com
- amankunawat4u@gmail.com  (this is the app owner / signed-in user)
- amanbaba.kumawat@gmail.com

Any non-whitelisted email is rejected with "This email is not authorized to access Insights".
OTP expires in 5 minutes. Max 3 resends per 10 minutes.

Note for testing agent: OTP is delivered to a real inbox via Resend and CANNOT be read programmatically.
Backend logs the generated OTP at INFO level is NOT enabled for security; to test verify-otp, the OTP
value can be read from the in-memory OTP_STORE only within the same process. For E2E, request-otp returns
200 on success; verify-otp requires the real code.
