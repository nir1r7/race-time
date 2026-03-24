import { ACTIVE_CIRCUIT } from "../../circuit-config";
import { CIRCUITS, CircuitKey } from "../../circuits";
import { DriverPosition } from "../../types";
// import { TEAM_COLORS } from "../../teamColors";
import "../../static/styles/circuit.css";

type Props = {
    positions: DriverPosition[];
    driverColours: Map<string, string>;
    activeCircuit: CircuitKey | null;
};

function Circuit({ positions, driverColours, activeCircuit }: Props) {
    const circuit =  CIRCUITS[activeCircuit ?? ACTIVE_CIRCUIT];

    return (
        <div className="circuit-track">
            <img
                className="circuit-svg"
                src={circuit.svgUrl}
                alt={circuit.name}
            />
            {positions.map((p) => {
                const color = driverColours.get(p.driver_code) ?? "#fff";
                const pastPoints = (p.trail ?? []).slice(0, -1);
                return [
                    ...pastPoints.map(([x, y], i) => {
                        const progress = (i + 1) / pastPoints.length;
                        const size = 6 + progress * 8;
                        return (
                            <div
                                key={`trail-${p.driver_number}-${i}`}
                                className="circuit-trail-dot"
                                style={{
                                    left: `${x * 100}%`,
                                    top: `${(1 - y) * 100}%`,
                                    backgroundColor: color,
                                    opacity: progress * 0.55,
                                    width: `${size}px`,
                                    height: `${size}px`,
                                }}
                            />
                        );
                    }),
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
                    </div>,
                ];
            })}
        </div>
    );
}

export default Circuit;
