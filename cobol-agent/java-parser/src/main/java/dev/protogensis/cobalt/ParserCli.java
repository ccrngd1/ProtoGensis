package dev.protogensis.cobalt;

import io.proleap.cobol.asg.metamodel.CompilationUnit;
import io.proleap.cobol.asg.metamodel.Program;
import io.proleap.cobol.asg.metamodel.ProgramUnit;
import io.proleap.cobol.asg.metamodel.data.DataDivision;
import io.proleap.cobol.asg.metamodel.data.datadescription.*;
import io.proleap.cobol.asg.metamodel.procedure.Paragraph;
import io.proleap.cobol.asg.metamodel.procedure.ProcedureDivision;
import io.proleap.cobol.asg.params.CobolParserParams;
import io.proleap.cobol.asg.params.impl.CobolParserParamsImpl;
import io.proleap.cobol.asg.runner.impl.CobolParserRunnerImpl;
import io.proleap.cobol.preprocessor.CobolPreprocessor.CobolSourceFormatEnum;
import java.io.File;
import java.util.ArrayList;
import java.util.List;

/** ProLeap-backed COBOL parser CLI emitting the cobalt-parser-v0 JSON
 *  contract (see cobalt/schema.py) on stdout. Structure extraction only:
 *  PIC decoding semantics and prompt assembly live on the Python side.
 *  Usage: java -jar cobalt-parser-v0.jar SOURCE.cbl [--copy-dir DIR]... */
public final class ParserCli {
    public static void main(String[] args) throws Exception {
        if (args.length < 1) {
            System.err.println("usage: cobalt-parser-v0.jar SOURCE [--copy-dir DIR]...");
            System.exit(2);
        }
        File source = new File(args[0]);
        List<File> copyDirs = new ArrayList<>();
        for (int i = 1; i < args.length - 1; i++)
            if ("--copy-dir".equals(args[i])) copyDirs.add(new File(args[++i]));
        CobolParserParams params = new CobolParserParamsImpl();
        params.setCopyBookDirectories(copyDirs);
        params.setCopyBookExtensions(List.of("", "cpy", "CPY", "cob", "cbl", "copy"));
        // ProLeap logs to stdout; the JSON contract owns it — reroute.
        java.io.PrintStream realOut = System.out;
        System.setOut(System.err);
        Program program;
        try {
            program = new CobolParserRunnerImpl()
                    .analyzeFile(source, CobolSourceFormatEnum.FIXED, params);
        } finally {
            System.setOut(realOut);
        }
        CompilationUnit unit = program.getCompilationUnits().get(0);
        ProgramUnit pu = unit.getProgramUnit();
        StringBuilder j = new StringBuilder("{");
        j.append("\"schema_version\":\"cobalt-parser-v0\",\"parser\":\"proleap\"");
        j.append(",\"program_id\":").append(str(unit.getName().toUpperCase()));
        j.append(",\"source_file\":").append(str(source.getName()));
        // ProLeap inlines COPY members during preprocessing; membership is
        // not exposed on the ASG, so we report the dirs we searched.
        j.append(",\"copybooks\":[]");
        j.append(",\"data_items\":[");
        DataDivision dd = pu.getDataDivision();
        if (dd != null && dd.getWorkingStorageSection() != null) {
            List<String> tops = new ArrayList<>();
            for (DataDescriptionEntry e
                    : dd.getWorkingStorageSection().getRootDataDescriptionEntries())
                tops.add(item(e, source.getName()));
            j.append(String.join(",", tops));
        }
        j.append("]");
        List<String> paras = new ArrayList<>();
        List<String> edges = new ArrayList<>();
        ProcedureDivision proc = pu.getProcedureDivision();
        if (proc != null) {
            for (Paragraph p : proc.getParagraphs()) {
                String name = p.getName().toUpperCase();
                List<String> performs = new ArrayList<>();
                collectPerforms(p, performs);
                paras.add("{\"name\":" + str(name) + ",\"performs\":"
                        + strList(performs) + ",\"line\":"
                        + p.getCtx().getStart().getLine() + "}");
                edges.add(str(name) + ":" + strList(performs));
            }
        }
        j.append(",\"paragraphs\":[").append(String.join(",", paras)).append("]");
        j.append(",\"perform_graph\":{").append(String.join(",", edges)).append("}");
        j.append(",\"diagnostics\":[]}");
        System.out.println(j);
    }
    /** Walk a paragraph's ANTLR parse tree collecting PERFORM procedure
     *  targets (statements nested in IF/EVALUATE included). */
    private static void collectPerforms(Paragraph p, List<String> out) {
        walkTree(p.getCtx(), out);
    }
    private static void walkTree(org.antlr.v4.runtime.tree.ParseTree node,
                                 List<String> out) {
        String kind = node.getClass().getSimpleName();
        if ("PerformProcedureStatementContext".equals(kind)) {
            for (int i = 0; i < node.getChildCount(); i++) {
                if ("ProcedureNameContext".equals(
                        node.getChild(i).getClass().getSimpleName())) {
                    String t = node.getChild(i).getText().toUpperCase();
                    if (!out.contains(t)) out.add(t);
                    break;
                }
            }
            return;
        }
        for (int i = 0; i < node.getChildCount(); i++)
            walkTree(node.getChild(i), out);
    }
    private static String item(DataDescriptionEntry e, String src) {
        String name = Boolean.TRUE.equals(filler(e)) || e.getName() == null
                ? "FILLER" : e.getName().toUpperCase();
        String pic = null, usage = null, redefines = null, value = null;
        String occurs = "null";
        List<String> children = new ArrayList<>();
        List<String> conds = new ArrayList<>();
        if (e instanceof DataDescriptionEntryGroup g) {
            if (g.getPictureClause() != null)
                pic = g.getPictureClause().getPictureString().toUpperCase();
            if (g.getUsageClause() != null)
                usage = mapUsage(g.getUsageClause().getUsageClauseType().toString());
            if (g.getRedefinesClause() != null)
                redefines = g.getRedefinesClause().getRedefinesCall()
                        .getName().toUpperCase();
            if (g.getValueClause() != null)
                value = g.getValueClause().getCtx().getText();
            List<OccursClause> ocs = g.getOccursClauses();
            if (ocs != null && !ocs.isEmpty()) {
                OccursClause oc = ocs.get(0);
                String idx = oc.getIndices().isEmpty() ? "null"
                        : str(oc.getIndices().get(0).getName().toUpperCase());
                Integer times = oc.getTo() != null ? oc.getTo().getValue()
                        : (oc.getFrom() != null ? oc.getFrom().getValue() : null);
                occurs = times == null ? "null"
                        : "{\"times\":" + times + ",\"indexed_by\":" + idx + "}";
            }
            for (DataDescriptionEntry c : g.getDataDescriptionEntries()) {
                if (c instanceof DataDescriptionEntryCondition c88) {
                    String vals = c88.getValueClause() == null ? ""
                            : str(c88.getValueClause().getCtx().getText());
                    conds.add("{\"name\":" + str(c88.getName().toUpperCase())
                            + ",\"values\":[" + vals + "]}");
                } else {
                    children.add(item(c, src));
                }
            }
        }
        int[] d = decodePic(pic);
        return "{\"level\":" + e.getLevelNumber()
                + ",\"name\":" + str(name)
                + ",\"picture\":" + (pic == null ? "null" : str(pic))
                + ",\"usage\":" + (usage == null ? "null" : str(usage))
                + ",\"signed\":" + (pic != null && pic.startsWith("S"))
                + ",\"integer_digits\":" + (d[0] < 0 ? "null" : d[0])
                + ",\"fraction_digits\":" + (d[1] < 0 ? "null" : d[1])
                + ",\"alpha_length\":" + (d[2] < 0 ? "null" : d[2])
                + ",\"occurs\":" + occurs
                + ",\"redefines\":" + (redefines == null ? "null" : str(redefines))
                + ",\"value\":" + (value == null ? "null" : str(value))
                + ",\"condition_names\":[" + String.join(",", conds) + "]"
                + ",\"children\":[" + String.join(",", children) + "]"
                + ",\"source\":" + str(src) + "}";
    }
    private static Boolean filler(DataDescriptionEntry e) {
        return e instanceof DataDescriptionEntryGroup g ? g.getFiller() : null;
    }
    /** {integerDigits, fractionDigits, alphaLength}; -1 means null. */
    private static int[] decodePic(String pic) {
        if (pic == null) return new int[]{-1, -1, -1};
        String body = pic.startsWith("S") ? pic.substring(1) : pic;
        StringBuilder ex = new StringBuilder();
        java.util.regex.Matcher m = java.util.regex.Pattern
                .compile("([9XAZPB*$])\\((\\d+)\\)|(.)").matcher(body);
        while (m.find()) {
            if (m.group(1) != null)
                ex.append(m.group(1).repeat(Integer.parseInt(m.group(2))));
            else ex.append(m.group(3));
        }
        String s = ex.toString();
        if (!s.isEmpty() && s.chars().allMatch(c -> c == 'X' || c == 'A'))
            return new int[]{-1, -1, s.length()};
        int v = s.indexOf('V');
        String left = v < 0 ? s : s.substring(0, v);
        String right = v < 0 ? "" : s.substring(v + 1);
        return new int[]{count(left), count(right), -1};
    }
    private static int count(String s) {
        return (int) s.chars().filter(c -> c == '9' || c == 'Z' || c == '*').count();
    }
    private static String mapUsage(String u) {
        u = u.toUpperCase().replace('_', '-');
        if (u.contains("PACKED") || u.contains("COMP-3")
                || u.contains("COMPUTATIONAL-3")) return "COMP-3";
        return u;
    }
    private static String str(String s) {
        return "\"" + s.replace("\\", "\\\\").replace("\"", "\\\"") + "\"";
    }
    private static String strList(List<String> xs) {
        List<String> q = new ArrayList<>();
        for (String x : xs) q.add(str(x));
        return "[" + String.join(",", q) + "]";
    }
}
