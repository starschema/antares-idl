"use strict";
var api = require("growatt");
var sparkplug = require("sparkplug-client");
var os = require("os");
var _ = require("lodash");
var flatten = require("flat");
var cron = require("node-cron");

require("dotenv").config();

const user = process.env.GROWATT_USER;
const password = process.env.GROWATT_PASSWORD;
const plantId = process.env.GROWATT_PLANT_ID;

const publishSchedule = process.env.PUBLISH_SCHEDULE || "*/5 * * * *";

const config = {
  serverUrl: `tcp://${process.env.MQTT_HOST || "mqtt"}:${
    process.env.MQTT_PORT || "1883"
  }`,
  groupId: "Solar",
  username: process.env.MQTT_USER || "admin",
  password: process.env.MQTT_PASSWORD || "public",
  edgeNode: os.hostname(),
  clientId: `Growatt Plant ${plantId}`,
  version: "spBv1.0",
};
var client = sparkplug.newClient(config);

const mapDataType = (v, k) => {
  var dataType;

  if (typeof v === "number" && v % 1 === 0) {
    dataType = "long";
  } else if (typeof v === "number") {
    dataType = "float";
  } else if (typeof v === "string") {
    dataType = "string";
  } else if (typeof v === "boolean") {
    dataType = "boolean";
  } else if (typeof v === "object") {
    dataType = "string";
    v = JSON.stringify(v);
  } else {
    dataType = "string";
  }

  return { name: k, value: v, type: dataType };
};

const retrieveGrowattData = async function () {
  const growatt = new api({});
  await growatt.login(user, password).catch((e) => {
    console.log("Cannot login to Growatt API:", e);
    throw e;
  });
  let getAllPlantData = await growatt.getAllPlantData({});
  await growatt.logout().catch((e) => {
    console.log("Cannot retrieve data from Growatt API:", e);
    throw e;
  });
  return getAllPlantData;
};

const getGrowattData = function (publishNodeData, publishDeviceData) {
  retrieveGrowattData()
    .then((data) => {
      const plant = data[plantId];
      const plantData = _.mapKeys(
        plant["plantData"],
        (v, k) => "plantData_" + k
      );
      const weather = flatten(plant["weather"]["data"]);

      const nodeData = _.assign(plantData, weather);
      if (publishNodeData) {
        publishNodeData({ metrics: _.map(nodeData, mapDataType) });
      }

      _.forIn(plant.devices, (device, deviceId) => {
        const deviceData = _.assign(
          device["deviceData"],
          device["historyLast"]
        );

        if (publishDeviceData) {
          publishDeviceData(deviceId, {
            timestamp: new Date(deviceData["calendar"]).getTime(),
            metrics: _.map(deviceData, mapDataType),
          });
        }
      });
    })
    .catch((err) => {
      console.log(err);
      return [null, null];
    });
};

// Create "birth" handler
client.on("birth", function () {
  getGrowattData(client.publishNodeBirth, client.publishDeviceBirth);
});

// Create node command handler
client.on("ncmd", function (payload) {
  const metrics = payload.metrics;

  if (metrics !== undefined && metrics !== null) {
    for (var i = 0; i < metrics.length; i++) {
      var metric = metrics[i];
      if (metric.name == "Node Control/Rebirth" && metric.value) {
        console.log("Received 'Rebirth' command");
        getGrowattData(client.publishNodeBirth, client.publishDeviceBirth);
      }
    }
  }
});

const run = function () {
  // getGrowattData(client.publishNodeData, client.publishDeviceData)

  cron.schedule(publishSchedule, () => {
    try {
      getGrowattData(client.publishNodeData, client.publishDeviceData);
    } catch (e) {
      console.log("ERROR:", e);
    }
  });
};

run();

//#client.stop()
