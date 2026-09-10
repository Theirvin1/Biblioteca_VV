UPDATE usuarios
SET password_hash = 'scrypt:32768:8:1$Uv8PNpgf7jgxBDz9$33b79136a522481caccc968f2de84a336667f92ea08871c504766e07c09a08510bde3f8a8a97581c039783bf340d42ea6c54d9a3f5ac1665d0a6deeeee9a5a20',
    debe_cambiar_password = FALSE,
    activo = TRUE,
    bloqueado = FALSE,
    intentos_fallidos = 0,
    fecha_bloqueo = NULL
WHERE username = 'estudiante';
SELECT length(password_hash) AS len FROM usuarios WHERE username = 'estudiante';
