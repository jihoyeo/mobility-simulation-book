/* global window */
import React, { useState, useEffect, useCallback } from "react";

import DeckGL from '@deck.gl/react';
import {Map} from 'react-map-gl';

import {AmbientLight, PointLight, LightingEffect} from '@deck.gl/core';
import {TripsLayer} from '@deck.gl/geo-layers';
import {IconLayer, ScatterplotLayer} from "@deck.gl/layers";

import Slider from "@mui/material/Slider";
import "../css/trip.css";

/* ============================================
   조명 및 재질 설정
============================================ */
const ambientLight = new AmbientLight({
  color: [255, 255, 255],
  intensity: 1.0
});

const pointLight = new PointLight({
  color: [255, 255, 255],
  intensity: 2.0,
  position: [-74.05, 40.7, 8000]
});

const lightingEffect = new LightingEffect({ambientLight, pointLight});

const material = {
  ambient: 0.1,
  diffuse: 0.6,
  shininess: 32,
  specularColor: [60, 64, 70]
};

const material2 = {
  ambient: 0.3,
  diffuse: 0.6,
  shininess: 32,
  specularCol: [60, 64, 70]
};

/* ============================================
   기본 테마 설정
============================================ */
const DEFAULT_THEME = {
  buildingColor: [228, 228, 228],
  buildingColor2: [255, 255, 255],
  trailColor0: [253, 128, 93],
  trailColor1: [23, 184, 190],
  material,
  material2,
  effects: [lightingEffect]
};

/* ============================================
   초기 지도 상태 설정
============================================ */
const INITIAL_VIEW_STATE = { 
  longitude: 127.136567, // 126.98 , -74
  latitude: 37.442322, // 37.57 , 40.72
  zoom: 15,
  pitch: 30,
  bearing: 0
};


/* ============================================
상수 및 헬퍼 함수
============================================ */
const ICON_MAPPING = {
  marker: { x: 0, y: 0, width: 128, height: 128, mask: true },
};

const minTime = 540;
const maxTime = 630;
const animationSpeed = 0.5;
const mapStyle = "mapbox://styles/spear5306/ckzcz5m8w002814o2coz02sjc";

const MAPBOX_TOKEN = `pk.eyJ1Ijoic2hlcnJ5MTAyNCIsImEiOiJjbG00dmtic3YwbGNoM2Zxb3V5NmhxZDZ6In0.ZBrAsHLwNihh7xqTify5hQ`;

// 애니메이션 시간 업데이트
const returnAnimationTime = (time) => {
    if (time > maxTime) {
      return minTime;
    } else {
      return time + 0.01 * animationSpeed;
    }
  };
  
  // 시간 값을 0으로 채우는 함수 (ex. 08:05 형식으로 표시)
  const addZeroFill = (value) => {
    const valueString = value.toString();
    return valueString.length < 2 ? "0" + valueString : valueString;
  };
  
  // 시간을 시/분 형식으로 변환
  const returnAnimationDisplayTime = (time) => {
    const hour = addZeroFill(parseInt((Math.round(time) / 60) % 24));
    const minute = addZeroFill(Math.round(time) % 60);
    return [hour, minute];
  };
  
  // 현재 애니메이션 시간에 활성화된 데이터 필터링
  const currData = (data, time) => {
    const arr = [];
    data.forEach((v) => {
      const timestamp = v.timestamp;
      const s_t = timestamp[0];
      const e_t = timestamp[timestamp.length - 1];
      if (s_t <= time && e_t >= time) {
        arr.push(v);
      }
    });
    return arr;
  };

/* ============================================
   메인 컴포넌트: Trip
============================================ */
const Trip = (props) => {
  // 애니메이션 시간을 관리하는 상태
  const [time, setTime] = useState(minTime);
  const [animation] = useState({});

  // 부모(APP.JS)로부터 전달받은 데이터
  const trip_car = props.trip_car;
  const trip_foot = props.trip_foot;
  const stop = props.stop;
  const point_car = currData(props.point_car, time); // 시간 기준으로 필터링된 차량 포인트
  // const point_car = props.point_car;
  // const trip = currData(props.trip, time);


  // 애니메이션 업데이트
  const animate = useCallback(() => {
    setTime((time) => returnAnimationTime(time));
    animation.id = window.requestAnimationFrame(animate);
  }, [animation]);

  useEffect(() => {
    animation.id = window.requestAnimationFrame(animate);
    return () => window.cancelAnimationFrame(animation.id);
  }, [animation, animate]);

  
  /* ============================================
     레이어 설정
  ============================================ */
  const layers = [
    // 정류장 아이콘 레이어
    new IconLayer({
      id: "location",
      data: stop,
      sizeScale: 7,
      iconAtlas:
        "https://raw.githubusercontent.com/visgl/deck.gl-data/master/website/icon-atlas.png",
      iconMapping: ICON_MAPPING,
      getIcon: d => "marker",
      getSize: 2,
      getPosition: d => d.coordinates,
      getColor: [255, 0, 0],
      opacity: 1,
      mipmaps: false, 
      pickable: true,
      radiusMinPixels: 2,
      radiusMaxPixels: 2,
    }),

    // 차량 경로 레이어
    new TripsLayer({  
      id: 'trips_car',
      data: trip_car,
      getPath: d => d.route,
      getTimestamps: d => d.timestamp,
      getColor: [255, 255, 0],
      opacity: 1,
      widthMinPixels: 7,
      capRounded : true,
      jointRounded : true,
      trailLength : 0.5,
      currentTime: time,
      shadowEnabled: false
    }),

    // 도보 경로 레이어
    new TripsLayer({  
      id: 'trips_foot',
      data: trip_foot,
      getPath: d => d.route,
      getTimestamps: d => d.timestamp,
      getColor: [255, 0, 255],
      opacity: 1,
      widthMinPixels: 7,
      capRounded : true,
      jointRounded : true,
      trailLength : 0.5,
      currentTime: time,
      shadowEnabled: false
    }),

    // 차량 포인트 레이어( 대기 하는 사람 )
    new ScatterplotLayer({
      id: 'scatterplot-layer',
      data: point_car,
      getPosition: d => d.coordinates,
      getFillColor: [255, 255, 255],
      getRadius: d => 3,
      getLineWidth: 3,
      radiusScale: 2,
      pickable: true,
      opacity: 0.5,
    }),

    // new ScatterplotLayer({
    //   id: "scatterplot-layer",
    //   data: trip,
    //   getPosition: (d) => {
    //     console.log("Route (first position):", d.route[0]); // 첫 번째 경로 좌표 확인
    //     return d.route[0];
    //   },
    //   getFillColor: (d) =>{
    //     console.log("Current time:", time, "Timestamp range:", d.timestamp[0], d.timestamp[1]);
    //     return time >= d.timestamp[0] && time < d.timestamp[1]
    //       ? [255, 255, 255] // 활성 상태
    //       : [0, 0, 0, 0]; // 비활성 상태
    //   },
    //   opacity: 1,
    // }),
    

  ];
  
  /* ============================================
     렌더링
  ============================================ */
  const SliderChange = (value) => {
    const time = value.target.value;
    setTime(time);
  };

  const [hour, minute] = returnAnimationDisplayTime(time);

  return (
    <div className="trip-container" style={{ position: "relative" }}>
      <DeckGL
        effects={DEFAULT_THEME.effects}
        initialViewState={INITIAL_VIEW_STATE}
        controller={true}
        layers={layers}
      >
        <Map mapStyle={mapStyle} mapboxAccessToken={MAPBOX_TOKEN} preventStyleDiffing={true}/>
      </DeckGL>
      <h1 className="time">TIME : {`${hour} : ${minute}`}</h1>
      <Slider
        id="slider"
        value={time}
        min={minTime}
        max={maxTime}
        onChange={SliderChange}
        track="inverted"
      />
    </div>
  );
};

export default Trip;
