import re

with open("C:/Users/zakro/ZCodeProject/assets/app.js", "r", encoding="utf-8") as f:
    content = f.read()

# Define the functions to remove
to_remove = [
    # state/utils
    "\\$", "pct", "parseKickoff", "effectiveStatus", "clockMinute", "fmtCountdown", "countdown",
    "teamBadge", "clean", "dot", "ouLineRow", "bioHtml", "teamFlag",
    
    # components
    "h2hBlock", "oddsBlock", "attackQualityBlock", "availabilityBlock", "upsetBlock", "contextBlock", "_contextInner",
    "marketsBlock", "ouBlock", "bttsBlock", "scenariosBlock", "shotsBlock", "cornersBlock", "cardsBlock",
    "renderStandings", "renderBracket", "ppTeam", "scorersVsBlock", "playerPropsBlock", "halftimeBlock",
    "renderPerf", "drawSpark"
]

for func in to_remove:
    # Match function definition and its block.
    # We use a simple regex but it might be hard to match curly braces in python regex.
    # Instead, we'll find "function NAME" and then use brace counting to remove it.
    pattern = re.compile(rf"function\s+{func}\s*\([^)]*\)\s*{{")
    match = pattern.search(content)
    if match:
        start = match.start()
        # count braces
        brace_count = 0
        in_string = False
        escape = False
        end = -1
        for i in range(start + len(match.group(0)) - 1, len(content)):
            char = content[i]
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    end = i + 1
                    break
        if end != -1:
            content = content[:start] + content[end:]
        else:
            print(f"Failed to find end of {func}")
    else:
        # Check if it was declared as an arrow function, e.g. const $ = id => ...
        pattern_arrow = re.compile(rf"const\s+{func}\s*=")
        match_arrow = pattern_arrow.search(content)
        if match_arrow:
            start = match_arrow.start()
            end = content.find("\n", start)
            content = content[:start] + content[end:]

# Now we need to handle the global variables that were moved to state.js
state_vars = ["MATCHES", "TAB", "GROUP", "SELECTED", "TOPPICKS", "LIVEFEED", "PNL", "STANDINGS", "H2H", "FAV_TEAMS"]
for var in state_vars:
    content = re.sub(rf"let\s+{var}\s*=\s*[^;]+;", "", content)
    content = re.sub(rf"const\s+{var}\s*=\s*[^;]+;", "", content)

# Remove the initial TIER_META if we want or keep it. It's not exported. Keep for now.

imports = """import { MATCHES, TAB, GROUP, SELECTED, TOPPICKS, LIVEFEED, PNL, STANDINGS, H2H, FAV_TEAMS, setMatches, setTab, setGroup, setSelected, setTopPicks, setLiveFeed, setPnl, setStandings, setH2h, setFavTeams } from './core/state.js';
import { $, pct, parseKickoff, effectiveStatus, clockMinute, fmtCountdown, countdown, teamBadge, clean, dot, ouLineRow, bioHtml } from './core/utils.js';
import { h2hBlock } from './components/h2h.js';
import { oddsBlock } from './components/odds.js';
import { attackQualityBlock, availabilityBlock, upsetBlock, contextBlock } from './components/context.js';
import { marketsBlock, ouBlock, bttsBlock } from './components/markets.js';
import { scenariosBlock } from './components/scenarios.js';
import { shotsBlock } from './components/shots.js';
import { cornersBlock } from './components/corners.js';
import { cardsBlock } from './components/cards.js';
import { renderStandings, renderBracket } from './components/standings.js';
import { ppTeam, scorersVsBlock, playerPropsBlock } from './components/playerProps.js';
import { halftimeBlock } from './components/halftime.js';
import { renderPerf, drawSpark } from './components/performance.js';

// Attach needed functions to window so inline HTML onclick handlers still work
window.openMatchByTeams = openMatchByTeams;
window.favBtn = favBtn;
window.toggleFav = toggleFav;
window.openSidebar = openSidebar;
window.closeSidebar = closeSidebar;
window.adminAction = adminAction;

"""

with open("C:/Users/zakro/ZCodeProject/assets/main.js", "w", encoding="utf-8") as f:
    f.write(imports + content)

print("Created main.js successfully.")
