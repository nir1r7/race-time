type Props = {
    targetDate: string;
    raceName: string;
    now: number;
};

function Countdown({ targetDate, raceName, now }: Props) {
    const remaining = Math.max(0, new Date(targetDate).getTime() - now);

    const totalSeconds = Math.floor(remaining / 1000);
    const days = Math.floor(totalSeconds / 86400);
    const hours = Math.floor((totalSeconds % 86400) / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;

    const pad = (n: number) => String(n).padStart(2, '0');

    return (
        <div className="countdown">
            <div className="countdown__label">Next Race: {raceName}</div>
            <div className="countdown__timer">
                {days}d {pad(hours)}:{pad(minutes)}:{pad(seconds)}
            </div>
        </div>
    );
}

export default Countdown;