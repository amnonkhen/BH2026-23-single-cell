import { useEffect, useMemo, useState } from "react";
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
  getConnection,
  searchRows,
  type ExperimentRow,
  type FacetField,
  type FacetSelection,
} from "./catalogQuery";

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

const FACET_PANELS: {
  field: FacetField;
  title: string;
  searchable?: boolean;
  open?: boolean;
  limit?: number;
}[] = [
  { field: "source", title: "Source" },
  { field: "organism", title: "Organism" },
  { field: "top_organ", title: "Top organ", searchable: true },
  {
    field: "tissue",
    title: "Tissue",
    searchable: true,
    open: false,
  },
  { field: "tissue_type", title: "Tissue type", open: false },
  { field: "assay", title: "Assay", searchable: true },
  { field: "disease", title: "Disease", searchable: true },
  {
    field: "cell_type",
    title: "Cell type",
    searchable: true,
  },
  {
    field: "development_stage",
    title: "Development stage",
    searchable: true,
    open: false,
  },
  { field: "suspension_type", title: "Suspension" },
  { field: "sex", title: "Sex" },
  {
    field: "study_journal",
    title: "Journal",
    searchable: true,
    open: false,
  },
];

function toggleValue(values: string[] | undefined, value: string): string[] {
  const current = values ?? [];
  return current.includes(value)
    ? current.filter((item) => item !== value)
    : [...current, value];
}

export default function App() {
  const [ready, setReady] = useState(false);
  const [bootError, setBootError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [facets, setFacets] = useState<FacetSelection>({});
  const [view, setView] = useState<ResultsView>("cards");
  const [page, setPage] = useState(0);
  const [rows, setRows] = useState<ExperimentRow[]>([]);
  const [found, setFound] = useState(0);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [searching, setSearching] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(true);

  useEffect(() => {
    let cancelled = false;
    getConnection()
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

  useEffect(() => {
    setPage(0);
  }, [debouncedQuery, facets]);

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
      Object.entries(facets).flatMap(([field, values]) =>
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

  const onApplyFacet = (field: string, value: string) => {
    if (value === "(none)") return;
    onToggleFacet(field as FacetField, value);
  };

  if (bootError) {
    return (
      <Container maxWidth="lg" sx={{ py: 4 }}>
        <Typography variant="h1" fontSize={{ xs: "2rem", md: "2.75rem" }} gutterBottom>
          scFair datasets
        </Typography>
        <Alert severity="error">
          {bootError}
          <Typography component="span" display="block" mt={1}>
            Export Parquet first: <code>python indexer/export_parquet.py</code>
          </Typography>
        </Alert>
      </Container>
    );
  }

  if (!ready) {
    return (
      <Container maxWidth="lg" sx={{ py: 4 }}>
        <Typography variant="h1" fontSize={{ xs: "2rem", md: "2.75rem" }} gutterBottom>
          scFair datasets
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
            scFair datasets
          </Typography>
          <Typography color="text.secondary" maxWidth="42rem">
            Browse and filter single-cell datasets by organism, tissue, assay, and more.
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
            {FACET_PANELS.map((panel) => (
              <ListItem key={panel.field} disableGutters disablePadding sx={{ display: "block" }}>
                <FacetList
                  field={panel.field}
                  title={panel.title}
                  query={debouncedQuery}
                  facets={facets}
                  selected={facets[panel.field] ?? []}
                  searchable={panel.searchable}
                  open={panel.open}
                  limit={panel.limit}
                  onToggle={(value) => onToggleFacet(panel.field, value)}
                />
              </ListItem>
            ))}
          </List>
        </Drawer>

        <Main open={filtersOpen}>
          <Container maxWidth="lg" sx={{ py: 2.5, pb: 8 }}>
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
                placeholder="Search titles, tissues, assays…"
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
                    label={`${field}: ${value}`}
                    maxWidth={220}
                    onDelete={() => onToggleFacet(field as FacetField, value)}
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
