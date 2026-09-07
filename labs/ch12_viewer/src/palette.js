// DTUMOS 프론트엔드가 쓰는 색을 그대로 옮겼습니다.
// 값을 바꾸면 화면의 색이 바뀝니다. 채점 대상은 아닙니다.

export const COLOR = {
  occupied: [214, 96, 40],    // 승객을 태우고 가는 중
  deadhead: [154, 164, 176],  // 승객을 태우러 가는 중 (공차)
  bus: [40, 120, 190],
  subway: [70, 150, 90],
  walk: [130, 130, 130],
  passenger: [47, 127, 191],  // 기다리는 승객
};

// cartype 이 10 이상이면 대중교통입니다. DTUMOS 의 코드 체계와 같습니다.
export const TRANSIT_COLOR = {
  10: COLOR.walk,
  11: COLOR.bus,
  12: COLOR.subway,
};
