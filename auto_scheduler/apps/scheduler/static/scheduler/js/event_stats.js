/*
Name: apps/scheduler/static/scheduler/js/event_stats.js
Description: Client-side charts for the Event Stats page (bar chart + monthly heatmap).
Authors: Audrey Pan
Created: November 23, 2025
Last Modified: November 24, 2025
*/

(() => {
  if (!window.Chart) return;

  /*  BAR CHART */
  const barCanvas = document.getElementById("typeChart");
  if (barCanvas && window.statsLabels && window.statsMinutes) {
    new Chart(barCanvas.getContext("2d"), {
      type: "bar",
      data: {
        labels: window.statsLabels,
        datasets: [
          {
            label: "Time spent (minutes)",
            data: window.statsMinutes
          }
        ]
      },
      options: {
        responsive: true,
        scales: { y: { beginAtZero: true } }
      }
    });
  }

  /* HEATMAP */
  const heatCanvas = document.getElementById("studyHeatmap");
  if (!heatCanvas || !window.heatmapData || !window.numHeatWeeks) return;

  const dayLabels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const bucketColors = ["#f2f2f2", "#dbeafe", "#bfdbfe", "#60a5fa", "#1d4ed8"];

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
          backgroundColor(ctx) {
            return bucketColors[ctx.raw.bucket] || bucketColors[0];
          },
          width({ chart }) {
            const a = chart.chartArea;
            if (!a) return 0;
            return (a.right - a.left) / 7 - 4;
          },

          height({ chart }) {
            const a = chart.chartArea;
            if (!a) return 0; 
            return (a.bottom - a.top) / window.numHeatWeeks - 4;
          }
        }
      ]
    },

    options: {
      responsive: false,
      maintainAspectRatio: false, // since canvas has fixed CSS height

      plugins: {
        legend: { display: false },
        tooltip: {
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
            callback: (v) => dayLabels[v] || ""
          },
          grid: { display: false }
        },

        y: {
          type: "linear",
          offset: true,
          reverse: true,
          min: -0.5,
          max: window.numHeatWeeks - 0.5,
          ticks: { display: false },
          grid: { display: false }
        }
      }
    },

    plugins: [heatmapBorder]
  });
})();
