from model.scrape_data import (
    SCRAPE_INTERVAL_SECONDS,
    get_checklist_left,
    get_checklist_right,
    get_events,
    get_indices,
    get_indices_updated_at,
    get_market_breadth,
    get_watchlist_data,
)

breadth = get_market_breadth()
watchlist = get_watchlist_data()
events = get_events()
checklist_left = get_checklist_left()
checklist_right = get_checklist_right()
