# PAD Diagnosis — Deployment Notes

The `data/pad_database.db` SQLite file is included in version control as the
seed database. On cloud platforms (Render free tier), the filesystem is
ephemeral — data written at runtime will reset on restart.

For persistent storage on cloud, consider upgrading to Render's paid disk
add-on, or migrating the database to PostgreSQL via SQLAlchemy's
`DATABASE_URL` environment variable.

