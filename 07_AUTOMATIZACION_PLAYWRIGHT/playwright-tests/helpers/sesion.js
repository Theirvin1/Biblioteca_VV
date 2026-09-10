// Helper de inicio de sesión. El login NO es uno de los 10 casos de
// prueba: aquí se usa únicamente como precondición reutilizable.

const CREDENCIALES_SEED = {
  bibliotecario: { username: 'bibliotecario', password: 'Biblio' },
  estudianteDemo: { username: 'estudiante', password: 'Estudiante' },
  gerente: { username: 'gerente', password: 'Gerente' },
};

/**
 * Inicia sesión con las credenciales dadas. Si el usuario tiene
 * `debe_cambiar_password=True` (por ejemplo, un estudiante recién
 * registrado por el bibliotecario con contraseña temporal), la app
 * redirige automáticamente a /cambiar-password; en ese caso, si se
 * proporcionó `passwordNueva`, este helper completa también ese cambio
 * para dejar la sesión lista y utilizable.
 *
 * Siempre pasa primero por /logout: así se puede llamar varias veces
 * dentro del mismo test para cambiar de usuario/rol (si ya hay una
 * sesión activa, /login redirige de inmediato sin mostrar el formulario).
 */
async function iniciarSesion(page, { username, password, passwordNueva } = {}) {
  if (typeof username !== 'string' || !username) {
    throw new Error(`iniciarSesion requiere "username" como string no vacío; se recibió: ${JSON.stringify(username)}`);
  }
  if (typeof password !== 'string' || !password) {
    throw new Error(
      `iniciarSesion requiere "password" como string no vacío; se recibió: ${JSON.stringify(password)}. ` +
      'Si es una contraseña temporal capturada de otro TC, verifica que se haya extraído y persistido correctamente.'
    );
  }

  await page.goto('/logout');
  await page.goto('/login');
  await page.fill('#username', username);
  await page.fill('#password', password);
  await page.click('input[type=submit]');

  if (page.url().includes('/cambiar-password')) {
    if (typeof passwordNueva !== 'string' || !passwordNueva) {
      throw new Error(
        `El usuario "${username}" debe cambiar su contraseña antes de continuar y no se ` +
        `proporcionó "passwordNueva" (string) al helper iniciarSesion(). Se recibió: ${JSON.stringify(passwordNueva)}`
      );
    }
    await page.fill('#password_actual', password);
    await page.fill('#password_nueva', passwordNueva);
    await page.fill('#password_confirmar', passwordNueva);
    await page.click('input[type=submit]');
  }
}

module.exports = { iniciarSesion, CREDENCIALES_SEED };
