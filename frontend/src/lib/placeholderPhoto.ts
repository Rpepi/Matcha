export function placeholderPhotoUrl(id: number): string {
    const index = (id % 70) + 1;
    return `https://i.pravatar.cc/600?img=${index}`;
}
