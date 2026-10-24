// MoovaTrack (prototipo): monitoreo biomecanico con datos SIMULADOS.
// Lee /api/moovatrack/lectura, cuenta repeticiones con histeresis y avisa
// cuando angulo o fuerza salen de los rangos terapeuticos.
import React, { useCallback, useEffect, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import {
  CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { ErrorSesion, pedirJson } from './api.js'

const INTERVALO_MS = 400
const MAX_PUNTOS = 75

const RANGOS_INICIALES = { anguloMin: 20, anguloMax: 160, fuerzaMax: 45 }
// Histeresis: una repeticion se cuenta al subir por encima de "alto" y volver
// por debajo de "bajo". Con un solo umbral, el ruido contaria repeticiones falsas.
const UMBRALES_INICIALES = { alto: 120, bajo: 60 }

function Indicador({ titulo, valor, unidad, alerta }) {
  return (
    <div className="col-12 col-md-4">
      <div className={`card card-moova shadow-sm text-center h-100 ${alerta ? 'border-danger' : ''}`}>
        <div className="card-body">
          <div className={`display-5 fw-bold ${alerta ? 'text-danger' : ''}`}>
            {valor}<small className="fs-5 text-muted"> {unidad}</small>
          </div>
          <div className="text-muted">{titulo}</div>
        </div>
      </div>
    </div>
  )
}

function CampoNumero({ id, etiqueta, valor, onCambio, min, max }) {
  return (
    <div className="col-6 col-md-2">
      <label className="form-label" htmlFor={id}>{etiqueta}</label>
      <input id={id} type="number" className="form-control" value={valor} min={min} max={max}
             onChange={(e) => onCambio(e.target.value === '' ? '' : Number(e.target.value))} />
    </div>
  )
}

function MoovaTrack({ urlDatos }) {
  const [corriendo, setCorriendo] = useState(false)
  const [lectura, setLectura] = useState(null)
  const [historial, setHistorial] = useState([])
  const [repeticiones, setRepeticiones] = useState(0)
  const [rangos, setRangos] = useState(RANGOS_INICIALES)
  const [umbrales, setUmbrales] = useState(UMBRALES_INICIALES)
  const [error, setError] = useState(null)
  const [sesionExpirada, setSesionExpirada] = useState(false)

  // Refs para que el temporizador siempre lea los valores vigentes.
  const faseRef = useRef('abajo')
  const umbralesRef = useRef(umbrales)
  umbralesRef.current = umbrales
  const contador = useRef(0)

  const leer = useCallback(async () => {
    try {
      const d = await pedirJson(urlDatos)
      setError(null)
      setLectura(d)
      contador.current += 1
      setHistorial((h) => [...h, { n: contador.current, angulo: d.angulo, fuerza: d.fuerza }].slice(-MAX_PUNTOS))

      const { alto, bajo } = umbralesRef.current
      if (faseRef.current === 'abajo' && d.angulo >= alto) {
        faseRef.current = 'arriba'
      } else if (faseRef.current === 'arriba' && d.angulo <= bajo) {
        faseRef.current = 'abajo'
        setRepeticiones((r) => r + 1)
      }
    } catch (e) {
      if (e instanceof ErrorSesion) {
        setSesionExpirada(true)
        setCorriendo(false)
      }
      setError(e.message)
    }
  }, [urlDatos])

  useEffect(() => {
    if (!corriendo) return undefined
    leer()
    const id = setInterval(leer, INTERVALO_MS)
    return () => clearInterval(id)
  }, [corriendo, leer])

  const reiniciar = () => {
    setRepeticiones(0)
    setHistorial([])
    setLectura(null)
    faseRef.current = 'abajo'
    contador.current = 0
  }

  const angulo = lectura ? lectura.angulo : null
  const fuerza = lectura ? lectura.fuerza : null
  const anguloFuera = angulo !== null && (angulo < rangos.anguloMin || angulo > rangos.anguloMax)
  const fuerzaFuera = fuerza !== null && fuerza > rangos.fuerzaMax
  const hayAlerta = anguloFuera || fuerzaFuera

  return (
    <div>
      <div className="alert alert-warning d-flex align-items-center gap-2 position-sticky top-0"
           role="status" style={{ zIndex: 5 }}>
        <i className="bi bi-cpu"></i>
        <strong>PROTOTIPO: datos simulados.</strong>
        <span>En producción llegan por Bluetooth HC-05 desde el Arduino (MPU-6050, FSR 402, Flex Sensor).</span>
      </div>

      {error && (
        <div className="alert alert-danger d-flex align-items-center gap-2" role="alert">
          <i className="bi bi-exclamation-circle"></i>
          <span>{error}</span>
          {sesionExpirada && <a href="/login" className="alert-link ms-2">Ir a iniciar sesión</a>}
        </div>
      )}

      {hayAlerta && (
        <div className="alert alert-danger d-flex align-items-center gap-2" role="alert">
          <i className="bi bi-exclamation-triangle-fill"></i>
          <strong>Fuera de rango:</strong>
          <span>
            {anguloFuera && `ángulo ${angulo}° (permitido ${rangos.anguloMin}°–${rangos.anguloMax}°) `}
            {fuerzaFuera && `fuerza ${fuerza} N (máximo ${rangos.fuerzaMax} N)`}
          </span>
        </div>
      )}

      <div className="d-flex gap-2 mb-4 flex-wrap">
        <button type="button" className={`btn ${corriendo ? 'btn-outline-secondary' : 'btn-moova'}`}
                onClick={() => setCorriendo((c) => !c)}>
          <i className={`bi ${corriendo ? 'bi-pause-fill' : 'bi-play-fill'}`}></i>{' '}
          {corriendo ? 'Pausar sesión' : 'Iniciar sesión'}
        </button>
        <button type="button" className="btn btn-outline-secondary" onClick={reiniciar}>
          <i className="bi bi-arrow-counterclockwise"></i> Reiniciar
        </button>
      </div>

      <div className="row g-4 mb-4">
        <Indicador titulo="Ángulo" valor={angulo === null ? '—' : angulo} unidad="°" alerta={anguloFuera} />
        <Indicador titulo="Fuerza" valor={fuerza === null ? '—' : fuerza} unidad="N" alerta={fuerzaFuera} />
        <Indicador titulo="Repeticiones" valor={repeticiones} unidad="" alerta={false} />
      </div>

      <div className="card card-moova shadow-sm mb-4">
        <div className="card-header panel-header d-flex align-items-center gap-2">
          <i className="bi bi-activity"></i>
          <h2 className="h5 mb-0">Lectura en tiempo real</h2>
        </div>
        <div className="card-body" style={{ height: 320 }}>
          {historial.length === 0 ? (
            <div className="text-center text-muted py-5">
              <i className="bi bi-play-circle me-2"></i> Pulsa «Iniciar sesión» para ver la gráfica.
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={historial}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="n" hide />
                <YAxis yAxisId="a" domain={[0, 180]} unit="°" />
                <YAxis yAxisId="f" orientation="right" domain={[0, 60]} unit=" N" />
                <Tooltip />
                <ReferenceLine yAxisId="a" y={rangos.anguloMin} stroke="#d9534f" strokeDasharray="4 4" />
                <ReferenceLine yAxisId="a" y={rangos.anguloMax} stroke="#d9534f" strokeDasharray="4 4" />
                <Line yAxisId="a" type="monotone" dataKey="angulo" name="Ángulo (°)" stroke="#337ab7"
                      dot={false} isAnimationActive={false} />
                <Line yAxisId="f" type="monotone" dataKey="fuerza" name="Fuerza (N)" stroke="#f0ad4e"
                      dot={false} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      <div className="card card-moova shadow-sm">
        <div className="card-header panel-header d-flex align-items-center gap-2">
          <i className="bi bi-sliders"></i>
          <h2 className="h5 mb-0">Rangos terapéuticos</h2>
        </div>
        <div className="card-body">
          <div className="row g-3">
            <CampoNumero id="mt-amin" etiqueta="Ángulo mín. (°)" valor={rangos.anguloMin} min={0} max={180}
                         onCambio={(v) => setRangos((r) => ({ ...r, anguloMin: v }))} />
            <CampoNumero id="mt-amax" etiqueta="Ángulo máx. (°)" valor={rangos.anguloMax} min={0} max={180}
                         onCambio={(v) => setRangos((r) => ({ ...r, anguloMax: v }))} />
            <CampoNumero id="mt-fmax" etiqueta="Fuerza máx. (N)" valor={rangos.fuerzaMax} min={0} max={200}
                         onCambio={(v) => setRangos((r) => ({ ...r, fuerzaMax: v }))} />
            <CampoNumero id="mt-alto" etiqueta="Umbral subida (°)" valor={umbrales.alto} min={0} max={180}
                         onCambio={(v) => setUmbrales((u) => ({ ...u, alto: v }))} />
            <CampoNumero id="mt-bajo" etiqueta="Umbral bajada (°)" valor={umbrales.bajo} min={0} max={180}
                         onCambio={(v) => setUmbrales((u) => ({ ...u, bajo: v }))} />
          </div>
          <p className="text-muted small mt-3 mb-0">
            Una repetición se cuenta cuando el ángulo supera el umbral de subida y luego baja del umbral de bajada.
          </p>
        </div>
      </div>
    </div>
  )
}

const raiz = document.getElementById('moovatrack-root')
if (raiz) {
  createRoot(raiz).render(<MoovaTrack urlDatos={raiz.dataset.url || '/api/moovatrack/lectura'} />)
}
