import "mapbox-gl/dist/mapbox-gl.css";
import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";

import Splash from "./components/Splash";
import Trip from "./components/Trip";
import "./css/app.css";

/*
  파일에서 데이터를 가져오는 예시 함수 (깃허브에서 데이터를 불러올 때 사용)
  자신의 깃허브 주소를 입력해야 하며, 현재는 주석처리 되어 있음
*/
/* const fetchData = (FilE_NAME) => {
  const res = axios.get(
    // 자신의 깃허브 주소 입력
    // https://raw.githubusercontent.com/'자신 깃허브 이름'/simulation/main/simulation/src/data/${FilE_NAME}.json
    `https://raw.githubusercontent.com/HNU209/simulation-class/main/simulation/src/data/${FilE_NAME}.json`
  );
  const data = res.then((r) => r.data);
  return data;
}; */

// fetchData 함수: public 폴더의 data에서 지정한 json 파일을 비동기로 불러옴
const fetchData = (FilE_NAME) => {
  return fetch(`${process.env.PUBLIC_URL}/data/${FilE_NAME}.json`)
    .then(response => response.json());
};

const App = () => {
  // trip: 여행 데이터 상태, setTrip: 상태 변경 함수
  const [trip, setTrip] = useState([]);

  // isloaded: 데이터 로딩 완료 여부, setIsLoaded: 상태 변경 함수
  const [isloaded, setIsLoaded] = useState(false);
  
  // getData 함수: trips 데이터를 비동기로 받아와 상태로 저장
  const getData = useCallback(async () => {
    const TRIP = await fetchData("trips");

    setTrip((prev) => TRIP); // 받아온 데이터를 trip 상태로 저장

    setIsLoaded(true); // 데이터 로딩 완료 표시
  }, []);

  // 컴포넌트가 마운트될 때 getData를 실행해 데이터 받아옴
  useEffect(() => {
    getData();
  }, [getData]);

  return (
    <div className="container">
      {/* 로딩 중일 때 Splash 컴포넌트 표시 */}
      {!isloaded && <Splash />}
      {/* 데이터 로딩 완료 시 Trip 컴포넌트로 trip 데이터 전달 */}
      {isloaded && (
        <Trip trip={trip} />
      )}
    </div>
  );
};

export default App;
