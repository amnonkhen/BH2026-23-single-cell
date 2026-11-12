import { useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  AppBar,
  Button,
  CircularProgress,
  Container,
  Divider,
  Drawer,
  IconButton,
  List,
  ListItem,
  Pagination,
  Stack,
  TextField,
  Toolbar,
  Tooltip,
  Typography,
} from "@mui/material";
import { styled } from "@mui/material/styles";
import ChevronLeftIcon from "@mui/icons-material/ChevronLeft";
import FilterListIcon from "@mui/icons-material/FilterList";
import SearchIcon from "@mui/icons-material/Search";
import InputAdornment from "@mui/material/InputAdornment";
import { EllipsisChip } from "./components/EllipsisChip";
import { FacetList } from "./components/FacetList";
import { ResultsPanel } from "./components/ResultsPanel";
import { ViewToggle, type ResultsView } from "./components/ViewToggle";
import {
  FACET_FIELDS,
  FIELD_TITLES,
  initCatalog,
  searchRows,
  termLabel,
  type ExperimentRow,
  type FacetField,
  type FacetSelection,
} from "./catalogQuery";
import { parseExploreUrl, replaceExploreUrl } from "./urlState";

const TITLE = "Single-cell datasets across species";

const PAGE_SIZE = 24;
const DRAWER_WIDTH = 300;

const Main = styled("main", {
  shouldForwardProp: (prop) => prop !== "open",
})<{ open?: boolean }>(({ theme, open }) => ({
  flexGrow: 1,
  minWidth: 0,
  transition: theme.transitions.create("margin", {
    easing: theme.transitions.easing.sharp,
    duration: theme.transitions.duration.leavingScreen,
  }),
  marginLeft: `-${DRAWER_WIDTH}px`,
  ...(open && {
    transition: theme.transitions.create("margin", {
      easing: theme.transitions.easing.easeOut,
      duration: theme.transitions.duration.enteringScreen,
    }),
    marginLeft: 0,
  }),
}));

const DrawerHeader = styled(Toolbar)(({ theme }) => ({
  minHeight: 48,
  paddingLeft: theme.spacing(1),
  paddingRight: theme.spacing(1),
  justifyContent: "flex-end",
  gap: theme.spacing(0.5),
}));

/** Filter panels open at start; the others are collapsed. */
const OPEN_PANELS = new Set<FacetField>([
  "organism",
  "tissue",
  "cell_type",
  "development_stage",
  "suspension_type",
]);

function toggleValue(values: string[] | undefined, value: string): string[] {
  const current = values ?? [];
  return current.includes(value)
    ? current.filter((item) => item !== value)
    : [...current, value];
}

export default function App() {
  const [ready, setReady] = useState(false);
  const [bootError, setBootError] = useState<string | null>(null);
  const initialUrl = useMemo(() => parseExploreUrl(window.location.search), []);
  const [query, setQuery] = useState(initialUrl.query);
  const [debouncedQuery, setDebouncedQuery] = useState(initialUrl.query);
  // Filters / layout from the URL, e.g. ?view=table&tissue=UBERON:0000955&organism=NCBITaxon:9606
  const [facets, setFacets] = useState<FacetSelection>(initialUrl.facets);
  const [view, setView] = useState<ResultsView>(initialUrl.view);
  const [page, setPage] = useState(initialUrl.page);
  const [rows, setRows] = useState<ExperimentRow[]>([]);
  const [found, setFound] = useState(0);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [searching, setSearching] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(true);

  useEffect(() => {
    let cancelled = false;
    initCatalog()
      .then(() => {
        if (!cancelled) {
          setReady(true);
          setBootError(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setBootError(err instanceof Error ? err.message : String(err));
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedQuery(query), 180);
    return () => window.clearTimeout(timer);
  }, [query]);

  // Reset pagination when the search changes, but keep a bookmarked ?page= on first load.
  const skipPageReset = useRef(true);
  useEffect(() => {
    if (skipPageReset.current) {
      skipPageReset.current = false;
      return;
    }
    setPage(0);
  }, [debouncedQuery, facets]);

  // Keep the address bar shareable when filters, layout, search or page change.
  useEffect(() => {
    replaceExploreUrl({ view, query: debouncedQuery, facets, page });
  }, [view, debouncedQuery, facets, page]);

  // Browser back/forward (and pasted history entries) restore the same state.
  useEffect(() => {
    const onPopState = () => {
      const next = parseExploreUrl(window.location.search);
      setView(next.view);
      setQuery(next.query);
      setDebouncedQuery(next.query);
      setFacets(next.facets);
      setPage(next.page);
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  useEffect(() => {
    if (!ready || view === "pivot") return;
    let cancelled = false;
    setSearching(true);
    searchRows(debouncedQuery, facets, {
      offset: page * PAGE_SIZE,
      limit: PAGE_SIZE,
    })
      .then((result) => {
        if (!cancelled) {
          setRows(result.rows);
          setFound(result.found);
          setSearchError(null);
          setSearching(false);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setSearchError(err instanceof Error ? err.message : String(err));
          setSearching(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [ready, debouncedQuery, facets, page, view]);

  const activeRefinements = useMemo(
    () =>
      (Object.entries(facets) as [FacetField, string[]][]).flatMap(([field, values]) =>
        values.map((value) => ({ field, value }))
      ),
    [facets]
  );

  const pageCount = Math.max(1, Math.ceil(found / PAGE_SIZE));

  const onToggleFacet = (field: FacetField, value: string) => {
    setFacets((prev) => {
      const next = { ...prev, [field]: toggleValue(prev[field], value) };
      if (!next[field]?.length) {
        delete next[field];
      }
      return next;
    });
  };

  /** Add a filter value (pivot cell or group click), without removing one already set. */
  const onApplyFacet = (field: FacetField, value: string) => {
    setFacets((prev) =>
      prev[field]?.includes(value) ? prev : { ...prev, [field]: [...(prev[field] ?? []), value] }
    );
  };

  if (bootError) {
    return (
      <Container maxWidth="lg" sx={{ py: 4 }}>
        <Typography variant="h1" fontSize={{ xs: "2rem", md: "2.75rem" }} gutterBottom>
          {TITLE}
        </Typography>
        <Alert severity="error">
          {bootError}
          <Typography component="span" display="block" mt={1}>
            Export the Parquet files first: <code>python scripts/export_explore.py</code> (see WP1/README.md)
          </Typography>
        </Alert>
      </Container>
    );
  }

  if (!ready) {
    return (
      <Container maxWidth="lg" sx={{ py: 4 }}>
        <Typography variant="h1" fontSize={{ xs: "2rem", md: "2.75rem" }} gutterBottom>
          {TITLE}
        </Typography>
        <Stack direction="row" spacing={1.5} alignItems="center">
          <CircularProgress size={22} />
          <Typography color="text.secondary">Loading catalog…</Typography>
        </Stack>
      </Container>
    );
  }

  return (
    <Stack sx={{ minHeight: "100vh" }}>
      <AppBar
        position="relative"
        color="transparent"
        elevation={0}
        sx={{
          zIndex: (theme) => theme.zIndex.drawer + 1,
          borderBottom: 1,
          borderColor: "divider",
          bgcolor: "rgba(255,255,255,0.72)",
          backdropFilter: "blur(10px)",
          color: "text.primary",
        }}
      >
        <Container maxWidth="lg" sx={{ py: 2.5 }}>
          <Typography variant="h1" fontSize={{ xs: "1.85rem", md: "2.5rem" }} gutterBottom>
            {TITLE}
          </Typography>
          <Typography color="text.secondary" maxWidth="42rem">
            Number of datasets per species and tissue, cell type or developmental stage, from
            CELLxGENE, scFAIR resources and Fenix, with ontology roll-up (composite-metazoan
            Uberon). Filters on tissue, cell type and stage include more specific terms.
          </Typography>
        </Container>
      </AppBar>

      <Stack direction="row" sx={{ flex: 1, overflow: "hidden" }}>
        <Drawer
          variant="persistent"
          anchor="left"
          open={filtersOpen}
          sx={{
            width: DRAWER_WIDTH,
            flexShrink: 0,
            "& .MuiDrawer-paper": {
              position: "relative",
              width: DRAWER_WIDTH,
              boxSizing: "border-box",
              border: 0,
              borderRight: 1,
              borderColor: "divider",
              bgcolor: "rgba(255,255,255,0.88)",
            },
          }}
        >
          <DrawerHeader variant="dense">
            <Typography variant="subtitle2" fontWeight={700} sx={{ flex: 1, pl: 0.5 }}>
              Filters
              {activeRefinements.length ? ` (${activeRefinements.length})` : ""}
            </Typography>
            <Button
              size="small"
              disabled={!activeRefinements.length && !query}
              onClick={() => {
                setQuery("");
                setFacets({});
              }}
            >
              Clear
            </Button>
            <Tooltip title="Collapse filters">
              <IconButton
                size="small"
                edge="end"
                aria-label="Collapse filters"
                onClick={() => setFiltersOpen(false)}
              >
                <ChevronLeftIcon />
              </IconButton>
            </Tooltip>
          </DrawerHeader>
          <Divider />
          <List dense disablePadding sx={{ overflowY: "auto", px: 1.5, py: 1 }}>
            {FACET_FIELDS.map((field) => (
              <ListItem key={field} disableGutters disablePadding sx={{ display: "block" }}>
                <FacetList
                  field={field}
                  title={FIELD_TITLES[field]}
                  query={debouncedQuery}
                  facets={facets}
                  selected={facets[field] ?? []}
                  open={OPEN_PANELS.has(field)}
                  onToggle={(value) => onToggleFacet(field, value)}
                />
              </ListItem>
            ))}
          </List>
        </Drawer>

        <Main open={filtersOpen}>
          <Container maxWidth="xl" sx={{ py: 2.5, pb: 8 }}>
            <Stack
              direction={{ xs: "column", sm: "row" }}
              spacing={1.5}
              alignItems={{ sm: "center" }}
              mb={2}
            >
              {!filtersOpen ? (
                <Button
                  variant="outlined"
                  size="small"
                  startIcon={<FilterListIcon />}
                  onClick={() => setFiltersOpen(true)}
                  aria-expanded={false}
                  color={activeRefinements.length ? "primary" : "inherit"}
                  sx={{ flexShrink: 0 }}
                >
                  Filters
                  {activeRefinements.length ? ` (${activeRefinements.length})` : ""}
                </Button>
              ) : null}
              <TextField
                fullWidth
                size="small"
                type="search"
                placeholder="Search titles, DOIs, species, tissues, cell types…"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchIcon fontSize="small" />
                    </InputAdornment>
                  ),
                }}
              />
              <ViewToggle value={view} onChange={setView} />
            </Stack>

            {activeRefinements.length ? (
              <Stack direction="row" flexWrap="wrap" useFlexGap gap={1} mb={2}>
                {activeRefinements.map(({ field, value }) => (
                  <EllipsisChip
                    key={`${field}:${value}`}
                    label={`${FIELD_TITLES[field]}: ${termLabel(field, value)}`}
                    maxWidth={220}
                    onDelete={() => onToggleFacet(field, value)}
                  />
                ))}
              </Stack>
            ) : null}

            <Typography variant="body2" color="text.secondary" mb={1.5}>
              {view === "pivot"
                ? "Pivot view"
                : searching
                  ? "Searching…"
                  : `${found.toLocaleString()} datasets`}
            </Typography>

            {searchError ? (
              <Alert severity="error" sx={{ mb: 2 }}>
                {searchError}
              </Alert>
            ) : null}

            <ResultsPanel
              view={view}
              rows={rows}
              query={debouncedQuery}
              facets={facets}
              onOpenHits={() => setView("table")}
              onApplyFacet={onApplyFacet}
            />

            {view !== "pivot" && found > PAGE_SIZE ? (
              <Stack alignItems="center" mt={3}>
                <Pagination
                  color="primary"
                  page={page + 1}
                  count={pageCount}
                  onChange={(_, next) => setPage(next - 1)}
                />
              </Stack>
            ) : null}
          </Container>
        </Main>
      </Stack>
    </Stack>
  );
}
