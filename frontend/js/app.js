import "./modules/legacy-app.js";

import { initAccionesMejora } from "./modules/acciones-mejora.js";
import { initContextoVectorial } from "./modules/contexto-vectorial.js";
import { initDashboard } from "./modules/dashboard.js";
import { initGestionAcademica } from "./modules/gestion-academica.js";
import { initMacroprocesos } from "./modules/macroprocesos.js";
import { initMetricas } from "./modules/metricas.js";
import { initPlanificacion } from "./modules/planificacion.js";
import { initReportes } from "./modules/reportes.js";
import { initSeguimientoSemanal } from "./modules/seguimiento-semanal.js";
import { initSilabos } from "./modules/silabos.js";

[
  initAccionesMejora,
  initContextoVectorial,
  initDashboard,
  initGestionAcademica,
  initMacroprocesos,
  initMetricas,
  initPlanificacion,
  initReportes,
  initSeguimientoSemanal,
  initSilabos
].forEach((initModule) => initModule());
