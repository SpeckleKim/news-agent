"""진입점: 스케줄러 기동 및 (선택) 웹 서버."""
import argparse
import logging
import sys
from pathlib import Path

# 프로젝트 루트를 path에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_config
from src.pipeline.run_pipeline import regroup_recent_articles, run_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def job(config: dict, max_raw: int = None) -> None:
    try:
        run_pipeline(config, max_raw=max_raw)
    except Exception as e:
        logger.exception("Pipeline error: %s", e)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="1회만 수집 후 종료")
    parser.add_argument("--config", default="config.yaml", help="config.yaml 경로")
    parser.add_argument("--clear", action="store_true", help="테스트용: DB 전체 삭제 후 수집")
    parser.add_argument("--max-raw", type=int, default=None, metavar="N", help="테스트용: 수집 건수를 N건으로 제한")
    parser.add_argument("--regroup-recent", type=int, default=None, metavar="N", help="최근 N건만 그룹 해제 후 재그룹 + 통합내용(합집합) LLM 반영")
    parser.add_argument("--list-groups", action="store_true", help="그룹화된 카드 목록(카드 제목 + 소속 기사) 출력")
    args = parser.parse_args()

    config = load_config(args.config)
    if args.list_groups:
        from src.storage.repository import Repository
        repo = Repository(config["storage"]["path"])
        groups = repo.list_groups_for_feed(limit=50)
        for i, g in enumerate(groups, 1):
            print(f"\n[카드 {i}] {g.merged_title or '(제목 없음)'}")
            print(f"  통합 요약: {(g.merged_summary or '')[:120]}...")
            for aid in (g.source_article_ids or []):
                a = repo.get_article(aid)
                if a:
                    print(f"  - {a.title[:60]}... ({a.source or '출처 없음'})")
            if not (g.source_article_ids or []):
                print("  (소속 기사 없음)")
        print(f"\n총 {len(groups)}개 카드(그룹)")
        return
    if args.regroup_recent is not None:
        from src.storage.repository import Repository
        repo = Repository(config["storage"]["path"])
        try:
            regroup_recent_articles(repo, config, limit=args.regroup_recent)
        except Exception as e:
            logger.exception("Regroup error: %s", e)
        return
    if args.clear:
        from src.storage.repository import Repository
        repo = Repository(config["storage"]["path"])
        repo.delete_all_data()
        logger.info("DB cleared (articles, duplicate_groups, related_chains)")
    if args.once:
        job(config, max_raw=args.max_raw)
        return

    from apscheduler.schedulers.blocking import BlockingScheduler
    interval = int(config.get("schedule", {}).get("interval_minutes", 60))
    scheduler = BlockingScheduler()
    scheduler.add_job(job, "interval", minutes=interval, args=[config], id="collect")
    logger.info("Scheduler started, interval=%s min", interval)
    scheduler.start()


if __name__ == "__main__":
    main()
