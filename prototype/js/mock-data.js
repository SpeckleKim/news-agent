/**
 * 프로토타입용 목업 데이터 (서버 없이 화면 확인용)
 */
window.MOCK_DATA = {
  feedItems: [
    {
      type: 'group',
      id: 'grp1',
      importance: 92,
      merged_title: '미래에셋증권, AI 기반 리테일 서비스 확대',
      merged_summary: '미래에셋증권이 자사 AX 플랫폼에 생성형 AI 기능을 도입해 고객 맞춤 리포트와 대화형 상담을 확대한다. 2025년 상반기부터 일부 지점에서 시범 운영 후 전면 rollout 예정이다.',
      published_at: '2025-03-12T09:30:00+09:00',
      category: '증권',
      keywords: ['미래에셋증권', 'AI', 'AX', '리테일'],
      source_urls: [
        { url: 'https://example.com/news/1', title: '매일경제', source: '매일경제' },
        { url: 'https://example.com/news/2', title: '한국경제', source: '한국경제' }
      ]
    },
    {
      type: 'article',
      id: 'art1',
      importance: 85,
      title: 'ChatGPT-5 출시, 멀티모달·코드 생성 강화',
      summary: 'OpenAI가 ChatGPT-5를 공개했다. 이미지·음성·코드 입력을 통합 처리하고, 긴 문맥과 추론 성능이 크게 향상되었다.',
      url: 'https://example.com/chatgpt5',
      source: 'TechCrunch',
      published_at: '2025-03-11T22:00:00+09:00',
      category: 'AI',
      keywords: ['ChatGPT', 'OpenAI', '멀티모달']
    },
    {
      type: 'article',
      id: 'art2',
      importance: 76,
      title: '클로드, 컴퓨터 유즈 기능 정식 출시',
      summary: 'Anthropic가 Claude의 컴퓨터 유즈(Computer Use) 기능을 정식 출시했다. 사용자 화면을 보며 작업을 수행할 수 있어 업무 자동화에 활용 가능하다.',
      url: 'https://example.com/claude-cu',
      source: 'VentureBeat',
      published_at: '2025-03-11T15:20:00+09:00',
      category: 'AI',
      keywords: ['Claude', 'Anthropic', 'Computer Use']
    },
    {
      type: 'group',
      id: 'grp2',
      importance: 80,
      merged_title: '국내 증권사 3사, IB 부문에 AI 애널리스트 도입',
      merged_summary: '국내 대형 증권사들이 투자은행(IB) 부문에 AI 애널리스트를 도입해 M&A·실사 보고서 초안 작성과 데이터 검증에 활용한다.',
      published_at: '2025-03-10T14:00:00+09:00',
      category: '금융',
      keywords: ['IB', '증권사', 'AI 애널리스트', 'M&A'],
      source_urls: [
        { url: 'https://example.com/ib1', title: '서울경제', source: '서울경제' },
        { url: 'https://example.com/ib2', title: '파이낸셜뉴스', source: '파이낸셜뉴스' }
      ]
    }
  ],
  articles: {
    art1: {
      id: 'art1',
      title: 'ChatGPT-5 출시, 멀티모달·코드 생성 강화',
      summary: 'OpenAI가 ChatGPT-5를 공개했다. 이미지·음성·코드 입력을 통합 처리하고, 긴 문맥과 추론 성능이 크게 향상되었다. 엔터프라이즈 API는 다음 달부터 제공된다.',
      body_snippet: '이번 버전에서는 100만 토큹 이상의 컨텍스트 윈도우와 강화된 코드 생성, 멀티모달 이해가 핵심이다.',
      url: 'https://example.com/chatgpt5',
      source: 'TechCrunch',
      published_at: '2025-03-11T22:00:00+09:00',
      category: 'AI',
      keywords: ['ChatGPT', 'OpenAI', '멀티모달'],
      duplicate_group_id: null
    },
    art2: {
      id: 'art2',
      title: '클로드, 컴퓨터 유즈 기능 정식 출시',
      summary: 'Anthropic가 Claude의 컴퓨터 유즈(Computer Use) 기능을 정식 출시했다. 사용자 화면을 보며 작업을 수행할 수 있어 업무 자동화·테스트 시나리오에 활용 가능하다.',
      body_snippet: 'Computer Use는 데스크톱 환경에서 클릭, 타이핑, 스크롤 등을 제어할 수 있으며, 보안과 프라이버시 정책을 충족하는 형태로 제공된다.',
      url: 'https://example.com/claude-cu',
      source: 'VentureBeat',
      published_at: '2025-03-11T15:20:00+09:00',
      category: 'AI',
      keywords: ['Claude', 'Anthropic', 'Computer Use'],
      duplicate_group_id: null
    }
  },
  groups: {
    grp1: {
      id: 'grp1',
      merged_title: '미래에셋증권, AI 기반 리테일 서비스 확대',
      merged_summary: '미래에셋증권이 자사 AX 플랫폼에 생성형 AI 기능을 도입해 고객 맞춤 리포트와 대화형 상담을 확대한다. 2025년 상반기부터 일부 지점에서 시범 운영 후 전면 rollout 예정이다. 금융위 원장도 증권사 AI 도입 가이드라인을 언급하며 긍정적 입장을 밝혔다.',
      merged_content: '미래에셋증권은 AX 플랫폼에 생성형 AI를 탑재해 고객 맞춤형 리포트 생성과 대화형 상담 기능을 강화한다. 2025년 상반기 일부 지점 시범 운영을 거쳐 전사 확대할 예정이며, 리테일 고객 대상 디지털 경험 개선이 목표다.\n\n금융위원회 측은 증권사 AI 활용 가이드라인을 검토 중이며, 고객 정보 보호와 투자 자문 경계를 명확히 하는 방향으로 정리할 계획이다. 미래에셋증권은 이에 맞춰 내부 가이드라인을 정비하고 있다.',
      published_at: '2025-03-12T09:30:00+09:00',
      category: '증권',
      keywords: ['미래에셋증권', 'AI', 'AX', '리테일'],
      source_urls: [
        { url: 'https://example.com/news/1', title: '미래에셋증권 AI 도입… AX에 생성형 AI 탑재', source: '매일경제' },
        { url: 'https://example.com/news/2', title: '금융위 "증권사 AI 가이드라인 검토 중"', source: '한국경제' }
      ],
      source_articles: [
        { id: 'art_s1', title: '미래에셋증권 AI 도입… AX에 생성형 AI 탑재', source: '매일경제', url: 'https://example.com/news/1' },
        { id: 'art_s2', title: '금융위 "증권사 AI 가이드라인 검토 중"', source: '한국경제', url: 'https://example.com/news/2' }
      ]
    },
    grp2: {
      id: 'grp2',
      merged_title: '국내 증권사 3사, IB 부문에 AI 애널리스트 도입',
      merged_summary: '국내 대형 증권사들이 투자은행(IB) 부문에 AI 애널리스트를 도입해 M&A·실사 보고서 초안 작성과 데이터 검증에 활용한다. 금융권 규제와 내부 가이드라인에 맞춰 검토 단계부터 적용 중이다.',
      merged_content: '서울경제 보도에 따르면 국내 3사가 IB 부문에 AI 애널리스트 도입을 확대하고 있다. M&A 타깃 분석, 실사 보고서 초안 작성, 재무 데이터 검증 등에 AI를 활용하며, 담당자 검토 후 최종 보고서로 정리하는 방식이다.\n\n파이낸셜뉴스는 증권사별로 AI 애널리스트 팀을 별도 구성하거나 기존 IB팀에 통합하는 등 운영 방식이 다르다고 전했다. 이데일리는 M&A 실사 단계에서 타깃사 재무제표·계약서 요약에 AI를 우선 적용하고, 규제 요건에 맞춰 내부 가이드라인을 정비 중인 것으로 보도했다.',
      published_at: '2025-03-10T14:00:00+09:00',
      category: '금융',
      keywords: ['IB', '증권사', 'AI 애널리스트', 'M&A'],
      source_urls: [
        { url: 'https://example.com/ib1', title: 'IB AI 도입 확대', source: '서울경제' },
        { url: 'https://example.com/ib2', title: '증권사 AI 애널리스트', source: '파이낸셜뉴스' },
        { url: 'https://example.com/ib3', title: 'M&A 실사에 AI 활용', source: '이데일리' }
      ],
      source_articles: [
        { id: 'art_s3', title: 'IB AI 도입 확대', source: '서울경제', url: 'https://example.com/ib1' },
        { id: 'art_s4', title: '증권사 AI 애널리스트', source: '파이낸셜뉴스', url: 'https://example.com/ib2' },
        { id: 'art_s5', title: 'M&A 실사에 AI 활용', source: '이데일리', url: 'https://example.com/ib3' }
      ]
    }
  },
  relatedHistory: {
    art1: {
      chains: [
        {
          chain_id: 'ch1',
          topic_label: 'OpenAI / ChatGPT 버전 업데이트',
          items: [
            { type: 'article', id: 'art_prev1', title: 'ChatGPT-4o 공개, 속도·비용 개선', published_at: '2025-01-15T10:00:00+09:00', position: 'prev' },
            { type: 'article', id: 'art1', title: 'ChatGPT-5 출시, 멀티모달·코드 생성 강화', published_at: '2025-03-11T22:00:00+09:00', position: 'current' },
            { type: 'article', id: 'art_next1', title: 'ChatGPT-5 API 엔터프라이즈 정식 오픈', published_at: '2025-04-01T00:00:00+09:00', position: 'next' }
          ]
        }
      ]
    },
    grp1: {
      chains: [
        {
          chain_id: 'ch2',
          topic_label: '미래에셋증권 AI·AX/DX 도입',
          items: [
            { type: 'group', id: 'grp_prev1', title: '미래에셋증권, 디지털 전환 1단계 완료', published_at: '2025-02-01T09:00:00+09:00', position: 'prev' },
            { type: 'group', id: 'grp1', title: '미래에셋증권, AI 기반 리테일 서비스 확대', published_at: '2025-03-12T09:30:00+09:00', position: 'current' },
            { type: 'article', id: 'art_next2', title: '미래에셋증권 AX 2.0, 전 지점 확대 예정', published_at: '2025-03-20T00:00:00+09:00', position: 'next' }
          ]
        }
      ]
    }
  }
};

/** API는 UTC로 전달. 프론트에서는 파싱 후 항상 한국시간(KST)으로 표시 */
function formatDate(isoStr) {
  if (!isoStr) return '';
  var s = String(isoStr).trim();
  if (s.length >= 10 && s[10] === 'T' && s.indexOf('Z') === -1 && !/[-+]\d{2}:?\d{2}$/.test(s))
    s = s + 'Z';
  var d = new Date(s);
  if (isNaN(d.getTime())) return isoStr;
  return d.toLocaleString('ko-KR', {
    timeZone: 'Asia/Seoul',
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
}

function getFeedItems() {
  return (window.MOCK_DATA && window.MOCK_DATA.feedItems) ? MOCK_DATA.feedItems : [];
}

function getArticle(id) {
  return (window.MOCK_DATA && window.MOCK_DATA.articles && window.MOCK_DATA.articles[id]) ? MOCK_DATA.articles[id] : null;
}

function getGroup(id) {
  return (window.MOCK_DATA && window.MOCK_DATA.groups && window.MOCK_DATA.groups[id]) ? MOCK_DATA.groups[id] : null;
}

function getRelatedHistory(articleOrGroupId) {
  var data = window.MOCK_DATA && window.MOCK_DATA.relatedHistory && window.MOCK_DATA.relatedHistory[articleOrGroupId];
  return data ? data.chains : [];
}

function getDetailUrl(item) {
  if (!item) return '#';
  return item.type === 'group' ? 'group.html?id=' + item.id : 'article.html?id=' + item.id;
}

/** 통합 요약/요약문에서 대표 제목용 첫 문장 추출 (최대 120자) */
window.firstSentence = function (str) {
  if (!str || !String(str).trim()) return '';
  var s = String(str).trim();
  var maxLen = 120;
  var idx = -1;
  if (s.indexOf('. ') !== -1) idx = idx === -1 ? s.indexOf('. ') : Math.min(idx, s.indexOf('. '));
  if (s.indexOf('.\n') !== -1) idx = idx === -1 ? s.indexOf('.\n') : Math.min(idx, s.indexOf('.\n'));
  if (s.indexOf('\n') !== -1) idx = idx === -1 ? s.indexOf('\n') : Math.min(idx, s.indexOf('\n'));
  if (s.indexOf('。') !== -1) idx = idx === -1 ? s.indexOf('。') : Math.min(idx, s.indexOf('。'));
  if (idx !== -1) s = s.substring(0, idx + 1).trim();
  return s.length > maxLen ? s.substring(0, maxLen) + '…' : s;
};
