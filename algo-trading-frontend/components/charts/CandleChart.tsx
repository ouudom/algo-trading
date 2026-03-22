'use client';

import React, { useEffect, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  createChart,
  createSeriesMarkers,
  CandlestickSeries,
  LineSeries,
  type IChartApi,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type ISeriesPrimitive,
  type IPrimitivePaneView,
  type IPrimitivePaneRenderer,
  type SeriesAttachedParameter,
  type SeriesType,
  type CandlestickSeriesOptions,
  type LineSeriesOptions,
  type DeepPartial,
  type Time,
  type Coordinate,
  type SeriesMarker,
} from 'lightweight-charts';
import type { CanvasRenderingTarget2D } from 'fancy-canvas';
import { getBacktestCandles, getBacktestTrades } from '@/lib/api';
import type { BacktestTrade } from '@/types';

// ─── Types ────────────────────────────────────────────────────────────────────

interface CandleChartProps {
  runId: string;
  height?: number;
}

// ─── Chart colours ────────────────────────────────────────────────────────────

const CHART_BG    = '#111827';
const GRID_COLOR  = '#1f2937';
const TEXT_COLOR  = '#6b7280';
const BULL_COLOR  = '#26a69a';
const BEAR_COLOR  = '#ef5350';
const EMA_FAST    = '#f59e0b';
const EMA_SLOW    = '#818cf8';

// ─── Helpers ──────────────────────────────────────────────────────────────────

function toSec(iso: string): number {
  return Math.floor(new Date(iso).getTime() / 1000);
}

// ─── Trade Zone Primitive ─────────────────────────────────────────────────────

interface ZonePixels {
  x1: Coordinate; x2: Coordinate;
  entryY: Coordinate; tpY: Coordinate; slY: Coordinate;
}

class TradeZoneRenderer implements IPrimitivePaneRenderer {
  constructor(private _zones: ZonePixels[]) {}

  draw(target: CanvasRenderingTarget2D): void {
    target.useBitmapCoordinateSpace(({ context: ctx, horizontalPixelRatio, verticalPixelRatio }) => {
      for (const z of this._zones) {
        const x1 = Math.round(z.x1 * horizontalPixelRatio);
        const x2 = Math.round(z.x2 * horizontalPixelRatio);
        const w  = x2 - x1;
        if (w <= 0) continue;

        const entryY = z.entryY * verticalPixelRatio;
        const tpY    = z.tpY   * verticalPixelRatio;
        const slY    = z.slY   * verticalPixelRatio;

        // TP zone — green
        ctx.fillStyle = 'rgba(34, 197, 94, 0.15)';
        const tpTop = Math.round(Math.min(tpY, entryY));
        const tpH   = Math.round(Math.abs(tpY - entryY));
        ctx.fillRect(x1, tpTop, w, tpH);

        // TP border line at TP price
        ctx.strokeStyle = 'rgba(34, 197, 94, 0.6)';
        ctx.lineWidth = 1;
        ctx.setLineDash([]);
        ctx.beginPath();
        ctx.moveTo(x1, Math.round(tpY));
        ctx.lineTo(x2, Math.round(tpY));
        ctx.stroke();

        // SL zone — red
        ctx.fillStyle = 'rgba(239, 68, 68, 0.15)';
        const slTop = Math.round(Math.min(slY, entryY));
        const slH   = Math.round(Math.abs(slY - entryY));
        ctx.fillRect(x1, slTop, w, slH);

        // SL border line at SL price
        ctx.strokeStyle = 'rgba(239, 68, 68, 0.6)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(x1, Math.round(slY));
        ctx.lineTo(x2, Math.round(slY));
        ctx.stroke();

        // Entry price dashed line
        ctx.strokeStyle = 'rgba(156, 163, 175, 0.7)';
        ctx.lineWidth = 1;
        ctx.setLineDash([4 * horizontalPixelRatio, 4 * horizontalPixelRatio]);
        const eY = Math.round(entryY);
        ctx.beginPath();
        ctx.moveTo(x1, eY);
        ctx.lineTo(x2, eY);
        ctx.stroke();
        ctx.setLineDash([]);
      }
    });
  }
}

class TradeZoneView implements IPrimitivePaneView {
  private _renderer = new TradeZoneRenderer([]);
  zOrder(): 'bottom' { return 'bottom'; }
  renderer(): IPrimitivePaneRenderer { return this._renderer; }
  update(zones: ZonePixels[]): void { this._renderer = new TradeZoneRenderer(zones); }
}

class TradePrimitive implements ISeriesPrimitive<Time> {
  private _view = new TradeZoneView();
  private _trades: BacktestTrade[] = [];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  private _chart: any = null;
  private _series: ISeriesApi<SeriesType> | null = null;
  private _requestUpdate: (() => void) | null = null;

  attached(params: SeriesAttachedParameter<Time, SeriesType>): void {
    this._series = params.series;
    this._chart  = params.chart;
    this._requestUpdate = params.requestUpdate;
    this.updateAllViews();
  }

  detached(): void {
    this._series = null;
    this._chart  = null;
    this._requestUpdate = null;
  }

  updateAllViews(): void {
    if (!this._series || !this._chart) return;
    const timeScale = this._chart.timeScale();

    const zones: ZonePixels[] = this._trades
      .map((t) => {
        const x1     = timeScale.timeToCoordinate(toSec(t.entry_time) as Time);
        const x2     = timeScale.timeToCoordinate(toSec(t.exit_time)  as Time);
        const entryY = this._series!.priceToCoordinate(t.entry_price);
        const tpY    = this._series!.priceToCoordinate(t.tp_price);
        const slY    = this._series!.priceToCoordinate(t.sl_price);
        if (x1 === null || x2 === null || entryY === null || tpY === null || slY === null) return null;
        return { x1, x2, entryY, tpY, slY };
      })
      .filter((z): z is ZonePixels => z !== null);

    this._view.update(zones);
  }

  paneViews(): readonly IPrimitivePaneView[] { return [this._view]; }

  setTrades(trades: BacktestTrade[]): void {
    this._trades = trades;
    this._requestUpdate?.();
  }
}

// ─── Marker builder ───────────────────────────────────────────────────────────

function buildMarkers(trades: BacktestTrade[]): SeriesMarker<Time>[] {
  const markers: SeriesMarker<Time>[] = [];

  for (const t of trades) {
    const isLong = t.direction === 1;

    markers.push({
      time:     toSec(t.entry_time) as Time,
      position: isLong ? 'belowBar' : 'aboveBar',
      color:    isLong ? '#22c55e' : '#ef4444',
      shape:    isLong ? 'arrowUp' : 'arrowDown',
      text:     isLong ? 'L' : 'S',
      size:     1,
    });

    const exitColor =
      t.exit_reason === 'TP'  ? '#22c55e'
      : t.exit_reason === 'SL' ? '#ef4444'
      : '#6b7280';

    markers.push({
      time:     toSec(t.exit_time) as Time,
      position: isLong ? 'aboveBar' : 'belowBar',
      color:    exitColor,
      shape:    'circle',
      text:     t.exit_reason ?? 'X',
      size:     1,
    });
  }

  markers.sort((a, b) => (a.time as number) - (b.time as number));
  return markers;
}

// ─── Inner chart ──────────────────────────────────────────────────────────────

interface ChartInnerProps {
  candles: ReturnType<typeof getBacktestCandles> extends Promise<infer T> ? T : never;
  trades: BacktestTrade[];
  height: number;
}

function ChartInner({ candles, trades, height }: ChartInnerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef     = useRef<IChartApi | null>(null);
  const candleRef    = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const emaFastRef   = useRef<ISeriesApi<'Line'> | null>(null);
  const emaSlowRef   = useRef<ISeriesApi<'Line'> | null>(null);
  const markersRef   = useRef<ISeriesMarkersPluginApi<Time> | null>(null);
  const primRef      = useRef<TradePrimitive | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      width:  containerRef.current.clientWidth,
      height,
      layout: {
        background:  { color: CHART_BG },
        textColor:   TEXT_COLOR,
        fontSize:    11,
      },
      grid: {
        vertLines: { color: GRID_COLOR },
        horzLines: { color: GRID_COLOR },
      },
      crosshair: {
        vertLine: { color: '#374151', labelBackgroundColor: '#1f2937' },
        horzLine: { color: '#374151', labelBackgroundColor: '#1f2937' },
      },
      rightPriceScale: { borderColor: GRID_COLOR },
      timeScale: {
        borderColor:    GRID_COLOR,
        timeVisible:    true,
        secondsVisible: false,
        fixLeftEdge:    true,
        fixRightEdge:   true,
      },
    });
    chartRef.current = chart;

    const candleOpts: DeepPartial<CandlestickSeriesOptions> = {
      upColor: BULL_COLOR, downColor: BEAR_COLOR,
      borderUpColor: BULL_COLOR, borderDownColor: BEAR_COLOR,
      wickUpColor: BULL_COLOR, wickDownColor: BEAR_COLOR,
    };
    const candleSeries = chart.addSeries(CandlestickSeries, candleOpts);
    candleRef.current  = candleSeries;

    const emaFastOpts: DeepPartial<LineSeriesOptions> = {
      color: EMA_FAST, lineWidth: 1,
      priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
    };
    const emaFastSeries = chart.addSeries(LineSeries, emaFastOpts);
    emaFastRef.current  = emaFastSeries;

    const emaSlowOpts: DeepPartial<LineSeriesOptions> = {
      color: EMA_SLOW, lineWidth: 1,
      priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
    };
    const emaSlowSeries = chart.addSeries(LineSeries, emaSlowOpts);
    emaSlowRef.current  = emaSlowSeries;

    candleSeries.setData(
      candles.map((b) => ({ time: b.time as Time, open: b.open, high: b.high, low: b.low, close: b.close })),
    );
    emaFastSeries.setData(
      candles.filter((b) => b.ema_fast !== null).map((b) => ({ time: b.time as Time, value: b.ema_fast! })),
    );
    emaSlowSeries.setData(
      candles.filter((b) => b.ema_slow !== null).map((b) => ({ time: b.time as Time, value: b.ema_slow! })),
    );

    // Trade zone primitive (drawn below candles)
    const prim = new TradePrimitive();
    prim.setTrades(trades);
    candleSeries.attachPrimitive(prim);
    primRef.current = prim;

    // Trade entry/exit markers
    markersRef.current = createSeriesMarkers(
      candleSeries,
      trades.length > 0 ? buildMarkers(trades) : [],
    );

    chart.timeScale().fitContent();

    const ro = new ResizeObserver(() => {
      if (containerRef.current) chart.applyOptions({ width: containerRef.current.clientWidth });
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current   = null;
      candleRef.current  = null;
      emaFastRef.current = null;
      emaSlowRef.current = null;
      markersRef.current = null;
      primRef.current    = null;
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!candleRef.current || !emaFastRef.current || !emaSlowRef.current) return;

    candleRef.current.setData(
      candles.map((b) => ({ time: b.time as Time, open: b.open, high: b.high, low: b.low, close: b.close })),
    );
    emaFastRef.current.setData(
      candles.filter((b) => b.ema_fast !== null).map((b) => ({ time: b.time as Time, value: b.ema_fast! })),
    );
    emaSlowRef.current.setData(
      candles.filter((b) => b.ema_slow !== null).map((b) => ({ time: b.time as Time, value: b.ema_slow! })),
    );
    if (markersRef.current) {
      markersRef.current.setMarkers(trades.length > 0 ? buildMarkers(trades) : []);
    }
    primRef.current?.setTrades(trades);
    chartRef.current?.timeScale().fitContent();
  }, [candles, trades]);

  return (
    <div>
      <div ref={containerRef} style={{ height }} />

      {/* Legend */}
      <div className="flex flex-wrap items-center gap-5 mt-3 px-1 text-xs text-gray-500">
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-3 rounded-sm opacity-70" style={{ background: 'rgba(34,197,94,0.3)', border: '1px solid rgba(34,197,94,0.6)' }} />
          TP zone
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-3 rounded-sm opacity-70" style={{ background: 'rgba(239,68,68,0.3)', border: '1px solid rgba(239,68,68,0.6)' }} />
          SL zone
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-1 rounded" style={{ background: BULL_COLOR }} />
          Bullish
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-1 rounded" style={{ background: BEAR_COLOR }} />
          Bearish
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-5 h-0.5 rounded" style={{ background: EMA_FAST }} />
          EMA fast
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-5 h-0.5 rounded" style={{ background: EMA_SLOW }} />
          EMA slow
        </span>
        <span className="flex items-center gap-1.5">
          <svg width="10" height="10" viewBox="0 0 10 10"><polygon points="5,0 10,10 0,10" fill="#22c55e" /></svg>
          Long entry
        </span>
        <span className="flex items-center gap-1.5">
          <svg width="10" height="10" viewBox="0 0 10 10"><polygon points="5,10 10,0 0,0" fill="#ef4444" /></svg>
          Short entry
        </span>
      </div>
    </div>
  );
}

// ─── Skeleton ─────────────────────────────────────────────────────────────────

function ChartSkeleton({ height }: { height: number }) {
  return (
    <div className="bg-gray-700/40 rounded animate-pulse" style={{ height }} aria-label="Loading chart" />
  );
}

// ─── Export ───────────────────────────────────────────────────────────────────

export default function CandleChart({ runId, height = 480 }: CandleChartProps) {
  const { data: candles, isLoading: candlesLoading } = useQuery({
    queryKey: ['backtest-candles', runId],
    queryFn:  () => getBacktestCandles(runId),
  });

  const { data: trades = [], isLoading: tradesLoading } = useQuery({
    queryKey: ['backtest-trades', runId],
    queryFn:  () => getBacktestTrades(runId),
  });

  if (candlesLoading || tradesLoading || !candles) return <ChartSkeleton height={height} />;

  if (candles.length === 0) {
    return (
      <div className="flex items-center justify-center rounded" style={{ height }}>
        <p className="text-sm text-gray-600">No candle data available</p>
      </div>
    );
  }

  return <ChartInner candles={candles} trades={trades} height={height} />;
}
