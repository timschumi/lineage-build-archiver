function human_readable_size(size) {
    const units = ["B", "KB", "MB", "GB"];
    const multiplier = Math.min(Math.floor(Math.log(size) / Math.log(1000)), units.length - 1);
    return (size / (1000 ** multiplier)).toFixed(multiplier > 0 ? 1 : 0) + " " + units[multiplier];
}
