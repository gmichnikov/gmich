(function () {
  var mapEl = document.getElementById("japan-recs-map");
  if (!mapEl || !window.JapanRecsMap) {
    return;
  }

  var places = [
    {
      name: "Arashiyama Monkey Park Iwatayama",
      day: "1",
      lat: 35.008938,
      lng: 135.674681,
      mapsUrl:
        "https://www.google.com/maps/search/?api=1&query=Arashiyama+Monkey+Park+Iwatayama",
      photoKey: "kyoto/monkey-park.jpg",
    },
    {
      name: "Arashiyama Bamboo Forest",
      day: "1",
      lat: 35.016742,
      lng: 135.671148,
      mapsUrl:
        "https://www.google.com/maps/search/?api=1&query=Arashiyama+Bamboo+Forest",
      photoKey: "kyoto/bamboo-forest.jpg",
    },
    {
      name: "Sabanji Ramen",
      day: "1",
      lat: 35.03742193700756,
      lng: 135.73078304235545,
      mapsUrl: "https://maps.app.goo.gl/6pHjonZUveMKox7a8",
      websiteUrl: "https://sabanji.com/en/index.html",
      photoKey: "kyoto/ramen-sabanji.jpg",
    },
    {
      name: "Kinkaku-ji (Golden Pavilion)",
      day: "1",
      lat: 35.0395,
      lng: 135.7285,
      mapsUrl:
        "https://www.google.com/maps/search/?api=1&query=Kinkaku-ji",
      wikipediaUrl: "https://en.wikipedia.org/wiki/Kinkaku-ji",
      photoKey: "kyoto/golden-temple.jpg",
    },
    {
      name: "Ginkaku-ji (Silver Pavilion)",
      day: "2",
      lat: 35.02667,
      lng: 135.79833,
      mapsUrl:
        "https://www.google.com/maps/search/?api=1&query=Ginkaku-ji",
      wikipediaUrl: "https://en.wikipedia.org/wiki/Ginkaku-ji",
      photoKey: "kyoto/silver-temple.jpg",
    },
    {
      name: "Omen Ginkaku-ji Udon",
      day: "2",
      lat: 35.02625018718538,
      lng: 135.79494026483994,
      mapsUrl: "https://maps.app.goo.gl/ZW3pJUCb4UYFARy29",
      websiteUrl: "https://omen.co.jp",
      photoKey: "kyoto/omen-udon.jpg",
    },
    {
      name: "Philosopher's Path",
      day: "2",
      path: [
        [35.0261, 135.79635],
        [35.0248, 135.79655],
        [35.0232, 135.7964],
        [35.0215, 135.79605],
        [35.0198, 135.79565],
        [35.018, 135.79525],
        [35.0162, 135.79485],
        [35.0145, 135.79445],
        [35.0129, 135.7941],
        [35.0117, 135.7937],
      ],
      mapsUrl:
        "https://www.google.com/maps/search/?api=1&query=Philosopher%27s+Path+Kyoto",
      wikipediaUrl: "https://en.wikipedia.org/wiki/Philosopher%27s_Walk",
      photoKey: "kyoto/philosophers-path.jpg",
    },
    {
      name: "Nanzen-ji",
      day: "2",
      lat: 35.01139,
      lng: 135.79417,
      mapsUrl:
        "https://www.google.com/maps/search/?api=1&query=Nanzen-ji",
      wikipediaUrl: "https://en.wikipedia.org/wiki/Nanzen-ji",
      photoKey: "kyoto/nanzen-ji.jpg",
    },
    {
      name: "Kyoto Tonkatsu Katsuda Shijokarasuma",
      day: "2",
      lat: 35.00126103247668,
      lng: 135.75944064822355,
      mapsUrl: "https://maps.app.goo.gl/zsGsidgpZU48C8Bw6",
      websiteUrl: "https://chikayado.jp/tonkatsukarasuma?_src=gbpmenu",
      photoKey: "kyoto/katsuda-shijokarasuma.jpg",
    },
    {
      name: "Nijō Castle",
      day: "3",
      lat: 35.014168,
      lng: 135.747498,
      mapsUrl: "https://maps.app.goo.gl/6sH5GopS6KWrYzAE8",
      wikipediaUrl: "https://en.wikipedia.org/wiki/Nijo_Castle",
      photoKey: "kyoto/nijo-castle.jpg",
    },
    {
      name: "Sushiro",
      day: "3",
      lat: 35.003741208208695,
      lng: 135.77421649564323,
      mapsUrl: "https://maps.app.goo.gl/djTVTXmPtW6pjcdb9",
      websiteUrl: "https://www.akindo-sushiro.co.jp/en/",
      photoKey: "kyoto/sushiro.jpg",
    },
    {
      name: "Nishiki Market",
      day: "3",
      lat: 35.00502620357052,
      lng: 135.7646169064146,
      mapsUrl: "https://maps.app.goo.gl/LkuRck4Vr7ze1y3M8",
      websiteUrl: "https://www.kyoto-nishiki.or.jp/en/",
      photoKey: "kyoto/nishiki-market.jpg",
    },
    {
      name: "Kiyomizu-dera",
      day: "3",
      lat: 34.995,
      lng: 135.785,
      mapsUrl: "https://maps.app.goo.gl/UFf46S5F7fPuSQFe6",
      wikipediaUrl: "https://en.wikipedia.org/wiki/Kiyomizu-dera",
      photoKey: "kyoto/kiyomizu-dera.jpg",
    },
    {
      name: "Fushimi Inari Taisha",
      day: "3",
      lat: 34.96722,
      lng: 135.77278,
      mapsUrl: "https://maps.app.goo.gl/qJHzAtWBRsJyTYxZA",
      wikipediaUrl: "https://en.wikipedia.org/wiki/Fushimi_Inari-taisha",
      photoKey: "kyoto/fushimi-inari-taisha.jpg",
    },
    {
      name: "Sushi no Musashi - Kyoto Station",
      day: "other",
      lat: 34.9846715476842,
      lng: 135.75940259330807,
      mapsUrl: "https://maps.app.goo.gl/qNn18kt4miKSM5zV7",
      websiteUrl: "https://sushinomusashi.com/",
      photoKey: "kyoto/sushi-no-musashi.jpg",
    },
    {
      name: "Boulangerie Cherish",
      day: "other",
      lat: 34.98793077291315,
      lng: 135.74112171849868,
      mapsUrl: "https://maps.app.goo.gl/N7ygAy7Ai3SUtc849",
    },
  ];

  var alwaysPlaces = [
    {
      name: "Dusit Thani Kyoto",
      kind: "hotel",
      lat: 34.99193355895671,
      lng: 135.7551218308406,
      mapsUrl: "https://maps.app.goo.gl/xkqzNPgZzgDWqcg17",
      websiteUrl: "https://www.dusit.com/dusitthani-kyoto/ja/",
    },
  ];

  JapanRecsMap.init({
    mapEl: mapEl,
    filterEl: document.querySelector(".japan-recs-day-filter"),
    listEl: document.getElementById("japan-recs-place-list"),
    places: places,
    alwaysPlaces: alwaysPlaces,
    dayOrder: ["1", "2", "3", "other"],
  });
})();
