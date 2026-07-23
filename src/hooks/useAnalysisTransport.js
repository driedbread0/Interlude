import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { gsap } from "gsap";

function clamp(value, min = 0, max = 1) {
  return Math.max(min, Math.min(max, Number(value) || 0));
}

function findWindow(windows, time) {
  if (!Array.isArray(windows)) return null;

  return windows.find((window) => {
    const start = Number(window?.start) || 0;
    const end = Number(window?.end) || start;
    return time >= start && time <= end;
  }) || null;
}

export default function useAnalysisTransport({ result, scopeRef }) {
  const duration = Math.max(0, Number(result?.project?.duration) || 0);
  const audioUrl = result?.project?.audio_url || null;
  const [position, setPosition] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [audioStatus, setAudioStatus] = useState(audioUrl ? "loading" : "preview");
  const [inspectionTime, setInspectionTime] = useState(null);
  const [inspectionMetric, setInspectionMetric] = useState(null);
  const [recentInspection, setRecentInspection] = useState(null);
  const [selectedEvidence, setSelectedEvidence] = useState(null);
  const audioRef = useRef(null);
  const frameRef = useRef(null);
  const positionRef = useRef(0);
  const visualSetterRef = useRef(null);
  const lastRenderRef = useRef(0);
  const fallbackOriginRef = useRef({ position: 0, time: 0 });
  const inspectionRef = useRef({ time: null, metric: null });
  const recentInspectionTimerRef = useRef(null);

  const setVisualProgress = useCallback((nextPosition) => {
    const normalized = clamp(nextPosition);

    if (visualSetterRef.current) {
      visualSetterRef.current(normalized);
    } else if (scopeRef.current) {
      scopeRef.current.style.setProperty("--analysis-progress", normalized);
    }
  }, [scopeRef]);

  useEffect(() => {
    if (!scopeRef.current) return undefined;

    visualSetterRef.current = gsap.quickSetter(scopeRef.current, "--analysis-progress");
    setVisualProgress(position);

    return () => {
      visualSetterRef.current = null;
    };
  }, [scopeRef, setVisualProgress]);

  useEffect(() => {
    setPlaying(false);
    setPosition(0);
    positionRef.current = 0;
    setInspectionTime(null);
    setInspectionMetric(null);
    setRecentInspection(null);
    inspectionRef.current = { time: null, metric: null };
    if (recentInspectionTimerRef.current) clearTimeout(recentInspectionTimerRef.current);
    setSelectedEvidence(null);
    setVisualProgress(0);

    if (!audioUrl) {
      audioRef.current = null;
      setAudioStatus("preview");
      return undefined;
    }

    const audio = new Audio(audioUrl);
    audio.preload = "metadata";
    audioRef.current = audio;
    setAudioStatus("loading");

    const handleMetadata = () => setAudioStatus("audio");

    const handleEnded = () => {
      setPlaying(false);
      setPosition(1);
      positionRef.current = 1;
      setVisualProgress(1);
    };
    const handleError = () => {
      setPlaying(false);
      audioRef.current = null;
      setAudioStatus("preview");
    };

    audio.addEventListener("loadedmetadata", handleMetadata);
    audio.addEventListener("ended", handleEnded);
    audio.addEventListener("error", handleError);

    return () => {
      audio.pause();
      audio.removeEventListener("loadedmetadata", handleMetadata);
      audio.removeEventListener("ended", handleEnded);
      audio.removeEventListener("error", handleError);
      audio.src = "";
      audioRef.current = null;
      if (recentInspectionTimerRef.current) clearTimeout(recentInspectionTimerRef.current);
    };
  }, [audioUrl, setVisualProgress]);

  useEffect(() => {
    if (!playing || duration <= 0) return undefined;

    fallbackOriginRef.current = {
      position: positionRef.current,
      time: performance.now(),
    };

    const update = (now) => {
      const audio = audioRef.current;
      let nextPosition;

      if (audio && Number.isFinite(audio.duration) && audio.duration > 0) {
        nextPosition = audio.currentTime / audio.duration;
      } else {
        const elapsed = (now - fallbackOriginRef.current.time) / 1000;
        nextPosition = fallbackOriginRef.current.position + elapsed / duration;
      }

      if (nextPosition >= 1) {
        nextPosition = 1;
        setVisualProgress(nextPosition);
        setPosition(nextPosition);
        positionRef.current = nextPosition;
        setPlaying(false);
        return;
      }

      setVisualProgress(nextPosition);

      if (now - lastRenderRef.current >= 80) {
        lastRenderRef.current = now;
        positionRef.current = nextPosition;
        setPosition(nextPosition);
      }

      frameRef.current = requestAnimationFrame(update);
    };

    frameRef.current = requestAnimationFrame(update);

    return () => {
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
      frameRef.current = null;
    };
  }, [duration, playing, setVisualProgress]);

  const seek = useCallback((nextPosition) => {
    const normalized = clamp(nextPosition);
    const audio = audioRef.current;

    if (audio) {
      const audioDuration = Number.isFinite(audio.duration) && audio.duration > 0 ? audio.duration : duration;
      audio.currentTime = normalized * audioDuration;
    }

    fallbackOriginRef.current = { position: normalized, time: performance.now() };
    positionRef.current = normalized;
    setPosition(normalized);
    setVisualProgress(normalized);
  }, [duration, setVisualProgress]);

  const seekToTime = useCallback((time) => {
    if (duration <= 0) return;
    seek(clamp(time / duration));
  }, [duration, seek]);

  const togglePlayback = useCallback(async () => {
    if (playing) {
      audioRef.current?.pause();
      setPlaying(false);
      return;
    }

    if (position >= 0.999) seek(0);

    if (audioRef.current) {
      try {
        await audioRef.current.play();
      } catch {
        audioRef.current = null;
        setAudioStatus("preview");
      }
    }

    setPlaying(true);
  }, [playing, position, seek]);

  const skip = useCallback((seconds) => {
    seekToTime(position * duration + seconds);
  }, [duration, position, seekToTime]);

  const inspectTime = useCallback((time, metric = null) => {
    if (recentInspectionTimerRef.current) {
      clearTimeout(recentInspectionTimerRef.current);
      recentInspectionTimerRef.current = null;
    }

    if (time === null || time === undefined) {
      const previous = inspectionRef.current;
      if (previous.time !== null) {
        setRecentInspection(previous);
        recentInspectionTimerRef.current = setTimeout(() => {
          setRecentInspection(null);
          recentInspectionTimerRef.current = null;
        }, 500);
      }
      inspectionRef.current = { time: null, metric: null };
      setInspectionTime(null);
      setInspectionMetric(null);
      return;
    }

    const next = { time: clamp(time, 0, duration), metric };
    inspectionRef.current = next;
    setRecentInspection(null);
    setInspectionTime(next.time);
    setInspectionMetric(metric);
  }, [duration]);

  useEffect(() => {
    const scope = scopeRef.current;
    if (!scope) return undefined;

    const clearInspectionOutsideEvidence = (event) => {
      if (inspectionRef.current.time === null) return;
      const target = event.target;
      if (target instanceof Element && target.closest(".metric-channel-plot, .signal-interaction, .chroma-lanes > div:first-child")) return;
      inspectTime(null);
    };

    scope.addEventListener("pointermove", clearInspectionOutsideEvidence, true);
    return () => scope.removeEventListener("pointermove", clearInspectionOutsideEvidence, true);
  }, [inspectTime, scopeRef]);

  const selectEvidence = useCallback((evidence, shouldSeek = false) => {
    setSelectedEvidence(evidence || null);

    if (evidence && shouldSeek) {
      const start = Number(evidence.start) || 0;
      const end = Number(evidence.end) || start;
      seekToTime((start + end) / 2);
    }
  }, [seekToTime]);

  const currentTime = position * duration;
  const evidenceTime = inspectionTime ?? currentTime;
  const focusMetric = inspectionMetric || selectedEvidence?.metric || recentInspection?.metric || null;
  const focusState = inspectionMetric
    ? "inspecting"
    : selectedEvidence?.metric
      ? "selected"
      : recentInspection?.metric
        ? "recent"
        : "rest";
  const activeWindows = useMemo(() => ({
    tempo: findWindow(result?.windows?.tempo, evidenceTime),
    pitch: findWindow(result?.windows?.pitch, evidenceTime),
    harmony: findWindow(result?.windows?.harmony, evidenceTime),
    dynamics: findWindow(result?.windows?.dynamics, evidenceTime),
  }), [evidenceTime, result?.windows]);

  return {
    activeWindows,
    audioAvailable: audioStatus === "audio",
    audioStatus,
    currentTime,
    duration,
    evidenceTime,
    focusMetric,
    focusState,
    inspectTime,
    inspectionMetric,
    inspectionTime,
    playing,
    position,
    recentInspection,
    seek,
    seekToTime,
    selectEvidence,
    selectedEvidence,
    skip,
    togglePlayback,
  };
}
