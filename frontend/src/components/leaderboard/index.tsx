import { LeaderBoardEntry } from "../../types";

type Props = {
    entries: LeaderBoardEntry[];
};

function Leaderboard({ entries }: Props) {
    return (
        <table>
            <thead>
                <tr>
                    <th>Pos</th>
                    <th>Driver</th>
                    <th>Team</th>
                    <th>Gap</th>
                    <th>Tyre</th>
                </tr>
            </thead>
            <tbody>
                {entries.length === 0 ? (
                    <tr>
                        <td colSpan={5}>No data</td>
                    </tr>
                ) : (
                    entries.map((entry) => (
                        <tr key={entry.driver_code}>
                            <td>{entry.position}</td>
                            <td>{entry.driver_code}</td>
                            <td>{entry.team}</td>
                            <td>{entry.gap_to_leader == null ? "—" : entry.gap_to_leader === 0 ? "LEADER" : `+${entry.gap_to_leader.toFixed(3)}`}</td>
                            <td>{entry.tire_compound}</td>
                        </tr>
                    ))
                )}
            </tbody>
        </table>
    );
}

export default Leaderboard;
