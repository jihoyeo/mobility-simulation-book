import "mapbox-gl/dist/mapbox-gl.css";
import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";

import Splash from "./components/Splash";
import Trip from "./components/Trip";
import "./css/app.css";


// const fetchData = (FilE_NAME) => {
//   const baseURL = process.env.NODE_ENV === "production"
//     ? `https://raw.githubusercontent.com/HNU209/simulation-class/main/simulation/src/data/${FilE_NAME}.json`
//     : `${process.env.PUBLIC_URL}/data/`;
  
//   return axios.get(`${baseURL}${FilE_NAME}.json`).then((r) => r.data);
// };

const fetchData = (FilE_NAME) => {
  return fetch(`${process.env.PUBLIC_URL}/data/${FilE_NAME}.json`)
    .then(response => response.json());
};

const App = () => {

  const [trip_car, setTripC] = useState([]);
  const [trip_foot, setTripF] = useState([]);
  const [stop, setStop] = useState([]);
  const [point_car, setPoint] = useState([]);

  const [isloaded, setIsLoaded] = useState(false);
  
  const getData = useCallback(async () => {

    // const TRIP = await Promise.all([
    //   fetchData("trips_car"),
    //   fetchData("trips_foot"),
    // ]);

    const TRIP_CAR = await fetchData("trips_car");
    const TRIP_FOOT = await fetchData("trips_foot");

    const STOP = await fetchData("icon_data");
    const POINT = await fetchData("trips_car_point");



    // setTrip((prev) => TRIP.flat());
    setTripC((prev) => TRIP_CAR);
    setTripF((prev) => TRIP_FOOT);
    setStop((prev) => STOP);
    setPoint((prev) => POINT);

    setIsLoaded(true);
  }, []);

  useEffect(() => {
    getData();
  }, [getData]);

  return (
    <div className="container">
      {!isloaded && <Splash />}
      {isloaded && (
        <Trip 
              trip_car={trip_car} 
              trip_foot={trip_foot} 
              stop={stop} 
              point_car={point_car} 
        
        />
      )}
    </div>
  );
};

export default App;
