PRAGMA busy_timeout = 30000;
UPDATE users SET password_hash = '$pbkdf2-sha256$29000$6R0DIGTMWWsNASDEeA8BgA$zN4z2Iwayya.3et6VlgG.LF/lC/gxrHuVID12aZ08tU' WHERE username = 'admin';
.COMMIT;
