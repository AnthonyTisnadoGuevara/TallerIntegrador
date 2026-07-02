const SUPABASE_URL = "https://zwjmqkatvveieibqkplc.supabase.co";
const SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inp3am1xa2F0dnZlaWVpYnFrcGxjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzk0MDQzMTAsImV4cCI6MjA5NDk4MDMxMH0.IfrPV0wvi3Wu1wU9SrYfvuCmH0O4CW2D7F4iMVBy8VI";
const DOMINIO_PERMITIDO = "";
const API_URL = ["localhost", "127.0.0.1"].includes(window.location.hostname)
  ? "http://127.0.0.1:8000"
  : "";

const supabaseAuth = supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

function correoPermitido(email) {
  if (!DOMINIO_PERMITIDO) return true;
  return email.toLowerCase().endsWith(DOMINIO_PERMITIDO);
}

function mostrarMensajeAuth(mensaje, tipo) {
  const contenedor = document.getElementById("authMessage");
  if (!contenedor) return;
  contenedor.textContent = mensaje;
  contenedor.className = `auth-message ${tipo}`;
}

function mostrarFormularioAuth(tipo) {
  const loginForm = document.getElementById("loginForm");
  const registerForm = document.getElementById("registerForm");
  const loginTab = document.getElementById("loginTab");
  const registerTab = document.getElementById("registerTab");

  if (!loginForm || !registerForm) return;

  const mostrarRegistro = tipo === "registro";
  loginForm.classList.toggle("hidden", mostrarRegistro);
  registerForm.classList.toggle("hidden", !mostrarRegistro);
  loginTab?.classList.toggle("active", !mostrarRegistro);
  registerTab?.classList.toggle("active", mostrarRegistro);
  mostrarMensajeAuth("", "");
}

async function iniciarSesion(event) {
  event.preventDefault();
  const email = document.getElementById("loginEmail").value.trim();
  const password = document.getElementById("loginPassword").value;

  if (!correoPermitido(email)) {
    mostrarMensajeAuth("Solo se permiten correos autorizados.", "error");
    return;
  }

  const { error } = await supabaseAuth.auth.signInWithPassword({ email, password });

  if (error) {
    mostrarMensajeAuth(error.message, "error");
    return;
  }

  window.location.href = "./index.html";
}

async function registrarUsuario(event) {
  event.preventDefault();
  const email = document.getElementById("registerEmail").value.trim();
  const password = document.getElementById("registerPassword").value;

  if (!correoPermitido(email)) {
    mostrarMensajeAuth("Solo se permiten correos autorizados.", "error");
    return;
  }

  const { error } = await supabaseAuth.auth.signUp({ email, password });

  if (error) {
    mostrarMensajeAuth(error.message, "error");
    return;
  }

  mostrarMensajeAuth("Registro realizado. Revisa tu correo para confirmar tu cuenta.", "success");
}

async function ingresarConGoogle() {
  const { error } = await supabaseAuth.auth.signInWithOAuth({
    provider: "google",
    options: {
      redirectTo: window.location.origin + "/index.html"
    }
  });

  if (error) {
    mostrarMensajeAuth("Google todavía no está configurado en Supabase o ocurrió un error.", "error");
  }
}

async function protegerPagina() {
  const { data } = await supabaseAuth.auth.getSession();

  if (!data.session) {
    window.location.href = "./login.html";
    return false;
  }

  const user = data.session.user;
  const span = document.getElementById("usuarioSesion");

  if (span) {
    span.textContent = user.email || "Usuario autenticado";
  }

  return true;
}

async function verificarSesionLogin() {
  const { data } = await supabaseAuth.auth.getSession();

  if (data.session) {
    window.location.href = "./index.html";
  }
}

async function cerrarSesion() {
  await supabaseAuth.auth.signOut();
  window.location.href = "./login.html";
}
