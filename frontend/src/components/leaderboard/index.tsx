import { LeaderBoardEntry } from "../../types";
// import { TEAM_COLORS } from "../../teamColors";
import "../../static/styles/leaderboard.css";

const TYRE_COLORS: Record<string, string> = {
    S: "#E8002D",
    M: "#FFC906",
    H: "#EBEBEB",
    I: "#39B54A",
    W: "#0067FF",
};

type Props = {
    entries: LeaderBoardEntry[];
    driverColours: Map<string, string>;
    raceName: string;
};

function Leaderboard({ entries, driverColours, raceName }: Props) {
    return (
        <div className="leaderboard-wrapper">
            <div className="leaderboard-header">
                <span className="leaderboard-header__badge">F1</span>
                <span className="leaderboard-header__title">{raceName}</span>
            </div>
            <table className="leaderboard">
                <tbody>
                    {entries.length === 0 ? (
                        <tr>
                            <td colSpan={4} className="lb-empty">No data</td>
                        </tr>
                    ) : (
                        entries.map((entry) => (
                            <tr key={entry.driver_code}>
                                <td className="lb-pos">{entry.position ?? '—'}</td>
                                <td className="lb-driver">
                                    <div className="lb-driver-inner">
                                        <span
                                            className="lb-team-bar"
                                            style={{ backgroundColor: driverColours.get(entry.driver_code) ?? "#ffffff" }}
                                        />
                                        <span className="lb-driver-code">{entry.driver_code}</span>
                                    </div>
                                </td>
                                <td className="lb-gap">
                                    {entry.gap_to_leader == null ? (
                                        "—"
                                    ) : entry.gap_to_leader === 0 ? (
                                        <span className="lb-gap--leader">LEADER</span>
                                    ) : (
                                        `+${entry.gap_to_leader.toFixed(3)}`
                                    )}
                                </td>
                                <td className="lb-tyre">
                                    <span
                                        className="lb-tyre-badge"
                                        style={{ backgroundColor: TYRE_COLORS[entry.tire_compound] ?? "#888" }}
                                    >
                                        {entry.tire_compound}
                                    </span>
                                </td>
                            </tr>
                        ))
                    )}
                </tbody>
            </table>
        </div>
    );
}

export default Leaderboard;
