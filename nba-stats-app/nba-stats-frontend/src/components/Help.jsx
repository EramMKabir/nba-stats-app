/*

Help.jsx

Function: To display help for the website.

Inputs:

None

Output:

HTML text that is meant to help understand the website.

Time complexity: O(1)

Space complexity: O(1)

#################################################################################
# Date modified              Modifier             What was modified             #
# 01/12/2026                 Eram Kabir           Initial and final development #
#################################################################################

*/

/* Libraries */

const Help = () => {

    return (
        <div className="help-grid" key="help">
            <article className="help-card help-intro">
                <span className="help-number">01</span>
                <h2>Pick a projection mode</h2>
                <p><strong>Player</strong> estimates one athlete’s output. <strong>Matchup</strong> projects team performance and a likely winner.</p>
            </article>
            <article className="help-card">
                <span className="help-number">02</span>
                <h2>Add the essentials</h2>
                <dl>
                    <div><dt>Player or team</dt><dd>Select the subject of your model.</dd></div>
                    <div><dt>Season year</dt><dd>Choose the NBA season to analyze.</dd></div>
                    <div><dt>Season type</dt><dd>Preseason, regular season, or playoffs.</dd></div>
                </dl>
            </article>
            <article className="help-card">
                <span className="help-number">03</span>
                <h2>Refine the signal</h2>
                <dl>
                    <div><dt>Opposing team</dt><dd>Optional. Adds head-to-head context.</dd></div>
                    <div><dt>Recent games</dt><dd>Optional. Limits analysis to the latest games.</dd></div>
                    <div><dt>Game date (optional)</dt><dd>Matchups only. Uses data from before the chosen date and accounts for team rest.</dd></div>
                    <div><dt>Venue</dt><dd>Matchups only. Choose whether the selected team or opponent is at home, or select a neutral court. Leave unspecified if unknown.</dd></div>
                </dl>
            </article>
            <article className="help-card help-wide">
                <span className="help-number">04</span>
                <h2>Read the output</h2>
                <p>Player projections appear as a stat grid. Matchup projections include a winner signal, modeled score, historical record, and scrollable player tables. To view an entire team without head-to-head weighting, leave the opponent blank.</p>
            </article>
            <aside className="system-note">
                <span className="live-dot" />
                <p><strong>Data note</strong> Player and team data refresh every 30 minutes. If lists appear stale, log out and back in. For security, access sessions refresh every 10 minutes.</p>
            </aside>
        </div>
    );
};

export default Help;
