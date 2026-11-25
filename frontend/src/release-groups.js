// One continental panel; genuinely different dates/currencies/offers stay distinct.
export function releaseGroups(releases) {
  const groups = [];
  let europe;
  for (const release of releases) {
    if (release.market !== 'Europa') {
      groups.push({ id: release.id, market: release.market, releases: [release] });
    } else if (europe) {
      europe.releases.push(release);
    } else {
      europe = { id: release.id, market: 'Europa', releases: [release] };
      groups.push(europe);
    }
  }
  return groups;
}
