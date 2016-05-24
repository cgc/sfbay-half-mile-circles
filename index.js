var ol = require('openlayers');
var fs = require('fs');
var fastCsv = require('fast-csv');
var csvParser = require('csv-parser');
var stream = require('stream');

var sfExtent = [-122.384591, 37.703211, -122.510850, 37.808675];
var sf = ol.extent.getCenter(sfExtent);
var halfMileInMeters = 804.672;
var wgs84Sphere = new ol.Sphere(6378137);

function stringStream(string) {
  // http://stackoverflow.com/questions/12755997/how-to-create-streams-from-string-in-node-js
  var s = new stream.Readable();
  s._read = function noop() {}; // redundant? see update below
  s.push(string);
  s.push(null);
  return s;
}

function makeLayer(csvStream, color) {
  var style = new ol.style.Style({
    stroke: new ol.style.Stroke({
      color: color,
      width: 1
    }),
    fill: new ol.style.Fill({
      color: color,
    })
  });

  var layer = new ol.layer.Vector({
    source: new ol.source.Vector(),
    style: [style],
  });

  var multi = new ol.geom.MultiPolygon();
  csvStream.pipe(csvParser()).on('data', function(stop) {
    var coord = [
      parseFloat(stop.stop_lon),
      parseFloat(stop.stop_lat),
    ];
    multi.appendPolygon(ol.geom.Polygon.circular(wgs84Sphere, coord, halfMileInMeters, 12));
  }).on('end', function() {
    layer.getSource().addFeature(
      new ol.Feature(multi.transform('EPSG:4326', 'EPSG:3857')));
  });

  return layer;
}

var raster = new ol.layer.Tile({
  source: new ol.source.Stamen({
    layer: 'toner'
  })
});

var sfmta = stringStream(fs.readFileSync('stops/sfmta.txt').toString());;
var actransit = stringStream(fs.readFileSync('stops/actransit.txt').toString());;
var bart = stringStream(fs.readFileSync('stops/bart.txt').toString());;
var caltrain = stringStream(fs.readFileSync('stops/caltrain.txt').toString());;
var vta = stringStream(fs.readFileSync('stops/vta.txt').toString());;
var samtrans = stringStream(fs.readFileSync('stops/samtrans.txt').toString());;

var map = new ol.Map({
  layers: [
    raster,
    makeLayer(sfmta, '#CA2163'),
    makeLayer(actransit, '#06674B'),
    makeLayer(samtrans, '#00529B'),
    makeLayer(vta, '#005882'),
    makeLayer(bart, '#00ADEF'),
    makeLayer(caltrain, '#E03A3E'),
  ],
  renderer: 'canvas',
  target: 'map',
  view: new ol.View({
    center: ol.proj.fromLonLat(sf),
    zoom: 12,
    maxZoom: 15,
    minZoom: 9,
  })
});

exports.map = map;
exports.ol = ol;
