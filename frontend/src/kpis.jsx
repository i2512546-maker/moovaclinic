// Panel de KPIs (admin). Lee /panel_admin/kpis.json y dibuja tarjetas y graficos.
import React, { useCallback, useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import {
  Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { ErrorSesion, pedirJson } from './api.js'

const soles = (n) =>
  'S/ ' + Number(n || 0).toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

function Tarjeta({ valor, titulo, clase = '' }) {
  return (
    <div className="col-6 col-md-3">
      <div className="card card-moova shadow-sm text-center h-100">
        <div className="card-body">
          <div className={`display-6 fw-bold ${clase}`}>{valor}</div>
          <div className="text-muted">{titulo}</div>
        </div>
      </div>
    </div>
  )
}

function Kpis({ urlDatos }) {
  const [desde, setDesde] = useState('')
  const [hasta, setHasta] = useState('')
  const [datos, setDatos] = useState(null)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(null)
  const [sesionExpirada, setSesionExpirada] = useState(false)

  const cargar = useCallback(async (d, h) => {
    setCargando(true)
    setError(null)
    const params = new URLSearchParams()
    if (d) params.set('desde', d)
    if (h) params.set('hasta', h)
    const sep = urlDatos.includes('?') ? '&' : '?'
    try {
      const r = await pedirJson(params.toString() ? `${urlDatos}${sep}${params}` : urlDatos)
      setDatos(r)
      setDesde(r.desde || '')
      setHasta(r.hasta || '')
      if (r.error) setError(r.error)
    } catch (e) {
      if (e instanceof ErrorSesion) setSesionExpirada(true)
      setError(e.message)
    } finally {
      setCargando(false)
    }
  }, [urlDatos])

  useEffect(() => { cargar('', '') }, [cargar])

  const resumen = datos && datos.resumen
  const terapeutas = (datos && datos.por_terapeuta) || []
  const grafico = terapeutas.map((t) => ({
    nombre: t.terapeuta_nombre,
    Total: Number(t.total_citas || 0),
    Completadas: Number(t.citas_completadas || 0),
    Ingresos: Number(t.ingresos || 0),
  }))

  return (
    <div>
      <div className="card card-moova shadow-sm mb-4">
        <div className="card-header panel-header d-flex align-items-center gap-2">
          <i className="bi bi-calendar-range"></i>
          <h2 className="h5 mb-0">Rango de fechas</h2>
        </div>
        <div className="card-body">
          <div className="row g-3 align-items-end">
            <div className="col-6 col-md-3">
              <label className="form-label" htmlFor="kpi-desde">Desde</label>
              <input id="kpi-desde" type="date" className="form-control" value={desde}
                     onChange={(e) => setDesde(e.target.value)} />
            </div>
            <div className="col-6 col-md-3">
              <label className="form-label" htmlFor="kpi-hasta">Hasta</label>
              <input id="kpi-hasta" type="date" className="form-control" value={hasta}
                     onChange={(e) => setHasta(e.target.value)} />
            </div>
            <div className="col-12 col-md-auto d-flex gap-2">
              <button type="button" className="btn btn-moova" disabled={cargando}
                      onClick={() => cargar(desde, hasta)}>
                <i className="bi bi-search"></i> Aplicar
              </button>
              <button type="button" className="btn btn-outline-secondary" disabled={cargando}
                      onClick={() => cargar('', '')}>
                <i className="bi bi-arrow-counterclockwise"></i> Últimos 30 días
              </button>
            </div>
          </div>
        </div>
      </div>

      {error && (
        <div className="alert alert-danger d-flex align-items-center gap-2" role="alert">
          <i className="bi bi-exclamation-circle"></i>
          <span>{error}</span>
          {sesionExpirada && <a href="/login" className="alert-link ms-2">Ir a iniciar sesión</a>}
        </div>
      )}

      {cargando && !datos && (
        <div className="text-center text-muted py-4">
          <i className="bi bi-hourglass-split me-2"></i> Cargando indicadores…
        </div>
      )}

      {resumen && (
        <>
          <div className="row g-4 mb-4" style={{ opacity: cargando ? 0.6 : 1 }}>
            <Tarjeta valor={resumen.total_citas} titulo="Total de citas" />
            <Tarjeta valor={resumen.citas_completadas} clase="text-success"
                     titulo={`Completadas (${resumen.tasa_completadas}%)`} />
            <Tarjeta valor={resumen.citas_programadas} titulo="Programadas" />
            <Tarjeta valor={resumen.citas_canceladas} clase="text-danger"
                     titulo={`Canceladas (${resumen.tasa_cancelacion}%)`} />
            <Tarjeta valor={soles(resumen.ingresos_confirmados)} titulo="Ingresos confirmados" />
            <Tarjeta valor={soles(resumen.ingresos_pendientes)} titulo="Ingresos pendientes" />
            <Tarjeta valor={resumen.paquetes_vendidos} titulo="Paquetes vendidos" />
            <Tarjeta valor={resumen.sesiones_consumidas} titulo="Sesiones consumidas" />
          </div>

          <div className="row g-4">
            <div className="col-12 col-lg-6">
              <div className="card card-moova shadow-sm h-100">
                <div className="card-header panel-header d-flex align-items-center gap-2">
                  <i className="bi bi-bar-chart"></i>
                  <h2 className="h5 mb-0">Citas por terapeuta</h2>
                </div>
                <div className="card-body" style={{ height: 320 }}>
                  {grafico.length === 0 ? (
                    <div className="text-center text-muted py-5">
                      <i className="bi bi-inbox me-2"></i> Sin datos en el rango seleccionado.
                    </div>
                  ) : (
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={grafico}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="nombre" />
                        <YAxis allowDecimals={false} />
                        <Tooltip />
                        <Legend />
                        <Bar dataKey="Total" fill="#6c8ebf" />
                        <Bar dataKey="Completadas" fill="#5cb85c" />
                      </BarChart>
                    </ResponsiveContainer>
                  )}
                </div>
              </div>
            </div>
            <div className="col-12 col-lg-6">
              <div className="card card-moova shadow-sm h-100">
                <div className="card-header panel-header d-flex align-items-center gap-2">
                  <i className="bi bi-cash-coin"></i>
                  <h2 className="h5 mb-0">Ingresos por terapeuta (S/)</h2>
                </div>
                <div className="card-body" style={{ height: 320 }}>
                  {grafico.length === 0 ? (
                    <div className="text-center text-muted py-5">
                      <i className="bi bi-inbox me-2"></i> Sin datos en el rango seleccionado.
                    </div>
                  ) : (
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={grafico}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="nombre" />
                        <YAxis />
                        <Tooltip formatter={(v) => soles(v)} />
                        <Bar dataKey="Ingresos" fill="#f0ad4e" />
                      </BarChart>
                    </ResponsiveContainer>
                  )}
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

const raiz = document.getElementById('kpis-root')
if (raiz) {
  createRoot(raiz).render(<Kpis urlDatos={raiz.dataset.url || '/panel_admin/kpis.json'} />)
}
