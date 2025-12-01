/*
Name: apps/scheduler/static/scheduler/js/event_stats.js
Description: Client-side charts for the Event Stats page (bar chart + monthly heatmap).
Authors: Audrey Pan
Created: November 23, 2025
Last Modified: November 30, 2025
*/

(() => {
  // If Chart.js is not loaded, don't do anything.
  if (!window.Chart) return;

    /*  BAR CHART: "Time spent (minutes)" by event type */
  const barCanvas = document.getElementById("typeChart");
  if (barCanvas && window.statsLabels && window.statsMinutes) {
    const ctx = barCanvas.getContext("2d");

    new Chart(ctx, {
      type: "bar",
      data: {
        labels: window.statsLabels,      // e.g. ["Lecture", "Homework", ...]
        datasets: [
          {
            label: "Time spent (minutes)",
            data: window.statsMinutes,    // e.g. [120, 45, ...]
            backgroundColor: "rgba(232, 201, 233, 0.9)",  // light pastel pink
            borderColor: "#ffffff",                      // crisp edge for contrast
            borderWidth: 1.2,
            hoverBackgroundColor: "rgba(220, 182, 224, 1)", // slightly darker on hover
            hoverBorderColor: "#ffffff"
          }
        ]
      },
      options: {
        responsive: true,
        plugins: {
          legend: {
            labels: {
              color: "#ffffff",          // legend text white
              font: { size: 14 }
            }
          }
        },
        scales: {
          x: {
            ticks: {
              color: "#ffffff",          // "Study Session" labels white
              font: { size: 13 }
            },
            grid: {
              color: "rgba(255,255,255,0.12)"
            }
          },
          y: {
            beginAtZero: true,
            ticks: {
              color: "#ffffff",          // y-axis numbers white
              font: { size: 13 }
            },
            grid: {
              color: "rgba(255,255,255,0.12)"
            }
          }
        }
      }
    });
  }


  /* HEATMAP: matrix chart of minutes studied per day, grouped by week */
  const heatCanvas = document.getElementById("studyHeatmap");
  // need a canvas, the heatmap data array, and the number of weeks to display.
  // heatmapData is an array of objects like:
  //   { x: dayIndex, y: weekIndex, date: "YYYY-MM-DD", minutes: 42, bucket: 2 }
  if (!heatCanvas || !window.heatmapData || !window.numHeatWeeks) return;

  const dayLabels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  // Buckets map to background colors (from "no study" to "most study").
  const bucketColors = ["#f2f2f2", "#e0b1cb", "#be95c4", "#9f86c0", "#5e548e"];

  // Custom plugin to draw a border around the whole heatmap area
  // (so the grid of cells has a clear outline).
  const heatmapBorder = {
    id: "heatmapBorder",
    afterDraw(chart) {
      const { ctx, chartArea } = chart;
      if (!chartArea) return;

      ctx.save();
      ctx.strokeStyle = "#cccccc";
      ctx.lineWidth = 2;
      ctx.strokeRect(
        chartArea.left,
        chartArea.top,
        chartArea.right - chartArea.left,
        chartArea.bottom - chartArea.top
      );
      ctx.restore();
    }
  };

  new Chart(heatCanvas.getContext("2d"), {
    type: "matrix",
    data: {
      datasets: [
        {
          label: "Study Heatmap",
          data: window.heatmapData,
          borderWidth: 1.1,
          borderColor: "#ccc",

          // Choose color based on the "bucket" (intensity) for that day.
          backgroundColor(ctx) {
            return bucketColors[ctx.raw.bucket] || bucketColors[0];
          },

          // Make each cell's width fill 7 columns with a small gap between days.
          width({ chart }) {
            const a = chart.chartArea;
            if (!a) return 0;
            return (a.right - a.left) / 7 - 4;
          },

          // Make each cell's height fill numHeatWeeks rows with a small gap between weeks.
          height({ chart }) {
            const a = chart.chartArea;
            if (!a) return 0;
            return (a.bottom - a.top) / window.numHeatWeeks - 4;
          }
        }
      ]
    },

    options: {
      // The canvas has a fixed height in CSS; keep Chart.js from forcing an aspect ratio.
      responsive: false,
      maintainAspectRatio: false,

      plugins: {
        legend: { display: false },
        tooltip: {
          // We only want the single line with date + minutes.
          callbacks: {
            title: () => "",
            label: (ctx) => {
              const d = ctx.raw;
              return `${d.date} – ${d.minutes} minute${d.minutes === 1 ? "" : "s"}`;
            }
          }
        }
      },

      scales: {
        x: {
          type: "linear",
          offset: true,
          min: -0.5,
          max: 6.5,
          ticks: {
            stepSize: 1,
            // Map numeric day index 0–6 to "Mon"–"Sun".
            callback: (v) => dayLabels[v] || ""
          },
          grid: { display: false }
        },

        y: {
          type: "linear",
          offset: true,
          // Reverse so week 0 is at the top and later weeks go downward.
          reverse: true,
          min: -0.5,
          max: window.numHeatWeeks - 0.5,
          // We don't show week numbers on the axis; the heatmap itself acts as the label.
          ticks: { display: false },
          grid: { display: false }
        }
      }
    },

    plugins: [heatmapBorder]
  });
})();
