export const tokenKey = 'ce-admin-token';
export const adminTokenKey = tokenKey;
export const studentTokenKey = 'ce-student-token';

export function getApiBase() {
  return (window.CE_API_BASE || '/api').replace(/\/$/, '');
}

export function escapeHtml(value) {
  return (value || '')
    .toString()
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

export function resolveAssetUrl(url, apiBase = getApiBase()) {
  if (!url) return '';
  if (url.startsWith('http://') || url.startsWith('https://')) return url;
  if (url.startsWith('/media/') || url.startsWith('/media-db/')) return `${apiBase}${url}`;
  return url;
}

export function formatDate(isoDate) {
  if (!isoDate) return 'Sin fecha';
  const parsed = new Date(isoDate);
  if (Number.isNaN(parsed.getTime())) return 'Sin fecha';
  return parsed.toLocaleDateString('es-CL', { year: 'numeric', month: 'short', day: 'numeric' });
}

export function initialsFor(name, fallback = 'IC') {
  return (name || fallback)
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() || '')
    .join('');
}

export function getToken() {
  return window.localStorage.getItem(tokenKey) || '';
}

export function clearToken() {
  window.localStorage.removeItem(tokenKey);
}

export function getStudentToken() {
  return window.localStorage.getItem(studentTokenKey) || '';
}

export function clearStudentToken() {
  window.localStorage.removeItem(studentTokenKey);
}

export function buildLoginUrl(returnTo = `${window.location.pathname}${window.location.search}`) {
  return `/login?returnTo=${encodeURIComponent(returnTo)}`;
}

export async function isAdminSession(apiBase = getApiBase()) {
  const token = getToken();
  if (!token) return false;

  try {
    const response = await fetch(`${apiBase}/admin/me`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    if (!response.ok) {
      clearToken();
      return false;
    }
    return true;
  } catch (error) {
    return false;
  }
}

export async function isStudentSession(apiBase = getApiBase()) {
  const token = getStudentToken();
  if (!token) return false;

  try {
    const response = await fetch(`${apiBase}/auth/me`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    if (!response.ok) {
      clearStudentToken();
      return false;
    }
    return true;
  } catch (error) {
    return false;
  }
}

export async function authorizedFetch(pathOrUrl, options = {}, apiBase = getApiBase()) {
  const headers = new Headers(options.headers || {});
  const token = getToken();
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  const url = pathOrUrl.startsWith('http://') || pathOrUrl.startsWith('https://')
    ? pathOrUrl
    : `${apiBase}${pathOrUrl}`;

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (response.status === 401) {
    clearToken();
  }

  return response;
}

export async function requestJson(pathOrUrl, options = {}, apiBase = getApiBase()) {
  const response = await authorizedFetch(pathOrUrl, options, apiBase);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || 'Error de servidor');
  }
  return payload;
}

export function renderAdminNotice(container, { isAdmin, sectionLabel }) {
  if (!container) return;

  if (isAdmin) {
    container.innerHTML = `
      <div class="rounded-2xl border border-utem-blue/20 bg-utem-blue/5 px-4 py-3 text-sm text-utem-blue">
        <strong>Modo admin activo.</strong> Puedes editar esta seccion directamente.
      </div>
    `;
    return;
  }

  const loginHref = buildLoginUrl();
  container.innerHTML = `
    <div class="rounded-2xl border border-utem-gray/40 bg-white px-4 py-3 text-sm text-utem-dark/70">
      Para administrar ${escapeHtml(sectionLabel || 'esta seccion')}, inicia sesion como admin.
      <a href="${loginHref}" class="ml-2 font-semibold text-utem-blue hover:underline">Entrar</a>
    </div>
  `;
}
