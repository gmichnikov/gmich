(function () {
  var mapEl = document.getElementById("japan-recs-map");
  if (!mapEl || !window.JapanRecsMap) {
    return;
  }

  var places = [
    {
      name: "Asakusa Shrine",
      day: "1",
      lat: 35.7151389,
      lng: 139.7974361,
      mapsUrl: "https://maps.app.goo.gl/NGLLqcTNW9ixPg9aA",
      wikipediaUrl: "https://en.wikipedia.org/wiki/Asakusa_Shrine",
    },
    {
      name: "Maguro-to-Shari Asakusa",
      day: "1",
      lat: 35.71333009937878,
      lng: 139.79358809614266,
      mapsUrl: "https://maps.app.goo.gl/HbT94E95YzbNdoko9",
      websiteUrl: "https://maguroshari.com/",
    },
    {
      name: "Meiji Jingu Shrine",
      day: "2",
      lat: 35.67611,
      lng: 139.69917,
      mapsUrl:
        "https://www.google.com/maps/search/?api=1&query=Meiji+Jingu+Shrine",
      wikipediaUrl: "https://en.wikipedia.org/wiki/Meiji_Shrine",
    },
    {
      name: "TsuruTonTan UDON NOODLE Brasserie SHIBUYA",
      day: "2",
      lat: 35.65844671780108,
      lng: 139.70216436918733,
      mapsUrl: "https://maps.app.goo.gl/kyTFpfF8RCHmJPim7",
    },
    {
      name: "Shibuya Crossing",
      day: "2",
      lat: 35.659526051399624,
      lng: 139.7005449531125,
      mapsUrl: "https://maps.app.goo.gl/zMBQ4gqaAXY2NEdo7",
      wikipediaUrl: "https://en.wikipedia.org/wiki/Shibuya_Crossing",
    },
    {
      name: "Tsukiji Peppers Cafe",
      day: "3",
      lat: 35.66527717036475,
      lng: 139.77015429380677,
      mapsUrl: "https://maps.app.goo.gl/DKihSHcYR2Zd5tZJ7",
      websiteUrl: "https://pepperscafe.tokyo/",
    },
    {
      name: "Tsukiji Outer Market",
      day: "3",
      lat: 35.664762572100486,
      lng: 139.7703117571338,
      mapsUrl: "https://maps.app.goo.gl/eKcKTy6bsr7yR9dz8",
      websiteUrl: "https://www.tsukiji.or.jp/english/",
    },
    {
      name: "BREIZH Café Crêperie Shinjuku Takashimaya",
      day: "4",
      lat: 35.6878526686546,
      lng: 139.70226976176534,
      mapsUrl: "https://maps.app.goo.gl/e13kbJus2xHx1ezv8",
      websiteUrl: "https://le-bretagne.com/creperie/shinjuku/",
    },
    {
      name: "Ginza Kagari - Soba",
      day: "4",
      lat: 35.671185268828545,
      lng: 139.76135095452554,
      mapsUrl: "https://maps.app.goo.gl/BQEmFVC4SUJDWDhb9",
      websiteUrl: "https://ginzakagari.thebase.in/",
    },
    {
      name: "Wagyu Yakiniku Ten Gamushara Akasaka",
      day: "5",
      lat: 35.66676082007621,
      lng: 139.73997943956655,
      mapsUrl: "https://maps.app.goo.gl/v5npXsthsUZGbwKX8",
      websiteUrl: "https://www.gamushara.info/",
    },
    {
      name: "Asakusa Gyukatsu",
      day: "5",
      lat: 35.71078791485017,
      lng: 139.79596854929756,
      mapsUrl: "https://maps.app.goo.gl/rnC86bXAoXVCA8bC6",
      websiteUrl: "https://tabelog.com/en/tokyo/A1311/A131102/13172454/",
    },
    {
      name: "teamLab Planets",
      day: "5",
      lat: 35.649034782877116,
      lng: 139.78999048131445,
      mapsUrl: "https://maps.app.goo.gl/pNW2r1RZusR7R6zDA",
      websiteUrl: "https://www.teamlab.art/jp/e/planets/",
    },
    {
      name: "Tokyo Skytree",
      day: "5",
      lat: 35.7100516905249,
      lng: 139.81070273748836,
      mapsUrl: "https://maps.app.goo.gl/moVsrRfDd3A2Ldn68",
      wikipediaUrl: "https://en.wikipedia.org/wiki/Tokyo_Skytree",
    },
    {
      name: "Isetan Shinjuku",
      day: "other",
      lat: 35.69161873077868,
      lng: 139.70465230960664,
      mapsUrl: "https://maps.app.goo.gl/MtyVPRcMgUWm2RWZ8",
      websiteUrl: "https://www.jocjapantravel.com/tokyo-shinjuku-isetan-food-floor/",
    },
  ];

  var alwaysPlaces = [
    {
      name: "Shangri-La Tokyo",
      kind: "hotel",
      lat: 35.682454369693914,
      lng: 139.76938322245218,
      mapsUrl: "https://maps.app.goo.gl/JicBADWAAyFbtd2JA",
    },
  ];

  JapanRecsMap.init({
    mapEl: mapEl,
    filterEl: document.querySelector(".japan-recs-day-filter"),
    listEl: document.getElementById("japan-recs-place-list"),
    places: places,
    alwaysPlaces: alwaysPlaces,
    dayOrder: ["1", "2", "3", "4", "5", "other"],
    fallbackView: { center: [35.6762, 139.6503], zoom: 12 },
  });
})();
