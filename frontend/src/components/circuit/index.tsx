import { DriverPosition } from "../../types";
import "../../static/styles/circuit.css";

type Props = {
    positions: DriverPosition[];
};

function Circuit({ positions }: Props) {
    return (
        <div className="circuit-track">
            {positions.map((p) => (
                <div
                    key={p.driver_number}
                    className="circuit-dot"
                    title={`${p.driver_code} (${p.x_norm.toFixed(2)}, ${p.y_norm.toFixed(2)})`}
                    style={{
                        left: `${p.x_norm * 100}%`,
                        top: `${(1 - p.y_norm) * 100}%`,
                    }}
                >
                    {p.driver_code}
                </div>
            ))}
        </div>
    );
}

export default Circuit;
