/**
 * 제품용 API 클라이언트 (실제 수집 데이터)
 * 프로토타입과 동일한 데이터 형식을 반환하여 기존 HTML/Alpine과 호환.
 */
(function () {
  var base = '/api';

  function getCookie(name) {
    var v = document.cookie.match('(^|;) ?' + name + '=([^;]*)(;|$)');
    return v ? v[2] : null;
  }

  async function fetchApi(path, opts) {
    var res = await fetch(base + path, { credentials: 'include', ...opts });
    if (res.status === 401) {
      window.location.href = '/login';
      throw new Error('Unauthorized');
    }
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  }

  /** 날짜별 페이지네이션: 뉴스가 있는 날짜 목록 (최신순) */
  window.getFeedDatesFromAPI = async function (filters) {
    var category = (filters && filters.category) || '';
    var keyword = (filters && filters.keyword) || '';
    var source = (filters && filters.source) || '';
    var q = '?';
    if (category) q += '&category=' + encodeURIComponent(category);
    if (keyword) q += '&keyword=' + encodeURIComponent(keyword);
    if (source) q += '&source=' + encodeURIComponent(source);
    if (q === '?') q = '';
    var data = await fetchApi('/feed/dates' + q);
    return data || { dates: [], total: 0 };
  };

  /** date 있으면 해당 일자만(중요도 순) 반환. date 없으면 최신 일자. */
  window.getFeedItemsFromAPI = async function (limit, offset, filters) {
    var category = (filters && filters.category) || '';
    var keyword = (filters && filters.keyword) || '';
    var source = (filters && filters.source) || '';
    var date = (filters && filters.date) || '';
    var q = '?';
    if (date) q += '&date=' + encodeURIComponent(date);
    if (category) q += '&category=' + encodeURIComponent(category);
    if (keyword) q += '&keyword=' + encodeURIComponent(keyword);
    if (source) q += '&source=' + encodeURIComponent(source);
    if (q === '?') q = '';
    var data = await fetchApi('/feed' + q);
    return data || { items: [], total: 0, date: null, date_label: null };
  };

  window.getFeedFiltersFromAPI = async function () {
    var data = await fetchApi('/feed/filters');
    return data || { categories: [], keywords: [], sources: [] };
  };

  /** 주요뉴스(최근 N일) */
  window.getHighlightsFromAPI = async function (days, topK, refresh) {
    var q = '?';
    if (typeof days === 'number') q += '&days=' + days;
    if (typeof topK === 'number') q += '&top_k=' + topK;
    if (refresh) q += '&refresh=1';
    if (q === '?') q = '';
    var data = await fetchApi('/highlights' + q);
    return data || { days: days || 7, top_k: topK || 12, editorial_summary: '', items: [], cached: false };
  };

  window.searchFromAPI = async function (query) {
    if (!query || !query.trim()) return { items: [], total: 0 };
    var data = await fetchApi('/search?q=' + encodeURIComponent(query.trim()));
    // search.html은 { items, total } 형태를 기대함
    return data || { items: [], total: 0 };
  };

  window.getArticleFromAPI = async function (id) {
    var data = await fetchApi('/articles/' + encodeURIComponent(id));
    return data || null;
  };

  window.getGroupFromAPI = async function (id) {
    var data = await fetchApi('/groups/' + encodeURIComponent(id));
    return data || null;
  };

  window.getRelatedHistoryFromAPI = async function (articleId) {
    var data = await fetchApi('/articles/' + encodeURIComponent(articleId));
    return (data && data.related_history && data.related_history.chains) ? data.related_history.chains : [];
  };

  window.getRelatedHistoryForGroupFromAPI = async function (groupId) {
    var data = await fetchApi('/groups/' + encodeURIComponent(groupId));
    if (!data || !data.related_history || !data.related_history.chains) return [];
    return data.related_history.chains;
  };

  window.requireAuthFromAPI = function () {
    if (!getCookie('news_agent_sid')) return false;
    return true;
  };
})();
