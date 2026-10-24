// Utilidad compartida: pide JSON al gateway y traduce los errores de sesion.
export class ErrorSesion extends Error {}

export async function pedirJson(url) {
  let resp
  try {
    resp = await fetch(url, {
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
    })
  } catch {
    throw new Error('No se pudo conectar con el servidor')
  }
  if (resp.status === 401 || resp.status === 403) {
    throw new ErrorSesion('Tu sesión expiró. Inicia sesión de nuevo.')
  }
  let datos = null
  try {
    datos = await resp.json()
  } catch {
    throw new Error('Respuesta inesperada del servidor')
  }
  if (!resp.ok) {
    throw new Error((datos && datos.error) || 'Error al consultar el servidor')
  }
  return datos
}
