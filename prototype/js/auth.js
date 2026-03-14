/**
 * 프로토타입용 로그인 체크.
 * - 제품(서버 localhost:6800): 서버가 이미 인증 후 페이지를 내려주므로 클라이언트에서는 리다이렉트하지 않음.
 * - 프로토타입(단독): sessionStorage로 로그인 여부 확인, 없으면 login.html로.
 */
var AUTH_KEY = 'news_agent_logged_in';

function isLoggedIn() {
  return sessionStorage.getItem(AUTH_KEY) === '1';
}

function setLoggedIn() {
  sessionStorage.setItem(AUTH_KEY, '1');
}

function requireAuth() {
  var onProductServer = typeof window !== 'undefined' && window.location && (window.location.port === '6800' || (window.location.hostname === 'localhost' && window.location.port === '6800'));
  if (onProductServer) return true;
  if (isLoggedIn()) return true;
  window.location.href = 'login.html';
  return false;
}

