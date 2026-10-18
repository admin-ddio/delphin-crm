"""Cross-cutting platform services shared by every module.

identity/      users, roles, sessions, auth tokens (tables only; sign-in logic is the auth module)
system/        settings, counters (human codes), saved views, integration configs
audit/         append-only audit log + secret redaction
activity/      activity feed events
notifications/ in-app notifications + preferences (delivery is an interface)
storage/       file storage interface
email/         e-mail sender interface
jobs/          background job interface + run history
"""
