import { DriverPosition } from "../../types";

type Props = {
    positions: DriverPosition[];
};

function Circuit({ positions }: Props) {
    return (
        <div>
            <p>Circuit visualization coming soon</p>
            {positions.map((p) => (
                <span key={p.driver_number}>{p.driver_code} </span>
            ))}
        </div>
    );
}

export default Circuit;
