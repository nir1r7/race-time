import { ACTIVE_CIRCUIT } from "../../circuit-config";
import { CIRCUITS } from "../../circuits";
import { DriverPosition, LeaderBoardEntry } from "../../types";
// import { TEAM_COLORS } from "../../teamColors";
import "../../static/styles/circuit.css";

type Props = {
    positions: DriverPosition[];
    leaderboard: LeaderBoardEntry[];
    driverColours: Map<string, string>;
};

function Circuit({ positions, leaderboard, driverColours }: Props) {
    const circuit = CIRCUITS[ACTIVE_CIRCUIT];

    const teamByDriver = new Map<string, string>(
        leaderboard.map((e) => [e.driver_code, e.team])
    );

    return (
        <div className="circuit-track">
            <img
                className="circuit-svg"
                src={circuit.svgUrl}
                alt={circuit.name}
            />
            {positions.map((p) => {
                const team = teamByDriver.get(p.driver_code);
                const color = driverColours.get(p.driver_code) ?? "#fff";
                return (
                    <div
                        key={p.driver_number}
                        className="circuit-dot"
                        title={`${p.driver_code} (${p.x_norm.toFixed(2)}, ${p.y_norm.toFixed(2)})`}
                        style={{
                            left: `${p.x_norm * 100}%`,
                            top: `${(1 - p.y_norm) * 100}%`,
                            backgroundColor: color,
                        }}
                    >
                        {p.driver_code}
                    </div>
                );
            })}
        </div>
    );
}

export default Circuit;
