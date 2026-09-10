// Generadores de datos de prueba VÁLIDOS (mismos algoritmos que
// app/validators.py) para evitar colisiones entre ejecuciones de la suite:
// cada corrida usa una cédula y un ISBN distintos, generados al azar pero
// con dígito verificador correcto.

/**
 * Genera una cédula ecuatoriana de persona natural válida (10 dígitos,
 * código de provincia 01-24, tercer dígito 0-5, dígito verificador módulo
 * 10). Replica app/validators.py:es_cedula_ecuatoriana_valida.
 */
function generarCedulaValida() {
  const provincia = Math.floor(Math.random() * 24) + 1; // 1..24
  const provinciaTexto = String(provincia).padStart(2, '0');

  const digitos = [parseInt(provinciaTexto[0], 10), parseInt(provinciaTexto[1], 10)];
  digitos.push(Math.floor(Math.random() * 6)); // tercer dígito: 0-5 (persona natural)
  for (let i = 0; i < 6; i++) {
    digitos.push(Math.floor(Math.random() * 10)); // completa los 9 primeros dígitos
  }

  const coeficientes = [2, 1, 2, 1, 2, 1, 2, 1, 2];
  let suma = 0;
  for (let i = 0; i < 9; i++) {
    let valor = digitos[i] * coeficientes[i];
    if (valor > 9) valor -= 9;
    suma += valor;
  }
  const verificador = (10 - (suma % 10)) % 10;
  digitos.push(verificador);

  return digitos.join('');
}

/**
 * Genera un ISBN-13 válido (13 dígitos, dígito verificador con pesos 1/3
 * alternados). Replica app/validators.py:es_isbn13_valido.
 */
function generarIsbnValido() {
  const digitos = [9, 7, 8]; // prefijo típico de ISBN-13, no es obligatorio pero es realista
  for (let i = 0; i < 9; i++) {
    digitos.push(Math.floor(Math.random() * 10));
  }

  let suma = 0;
  for (let i = 0; i < 12; i++) {
    suma += digitos[i] * (i % 2 === 0 ? 1 : 3);
  }
  const verificador = (10 - (suma % 10)) % 10;
  digitos.push(verificador);

  return digitos.join('');
}

/**
 * Genera un ISBN-13 con formato correcto (13 dígitos) pero dígito
 * verificador INCORRECTO, para probar que Isbn13Valido lo rechace.
 */
function generarIsbnConChecksumInvalido() {
  const valido = generarIsbnValido();
  const ultimoDigito = parseInt(valido[12], 10);
  const digitoAlterado = (ultimoDigito + 1) % 10; // garantiza que sea distinto al correcto
  return valido.slice(0, 12) + digitoAlterado;
}

module.exports = {
  generarCedulaValida,
  generarIsbnValido,
  generarIsbnConChecksumInvalido,
};
