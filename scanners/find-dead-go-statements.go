// Finds statements that follow t.Fatal/t.Fatalf/t.FailNow/t.Skip in the same
// block. Those calls end the goroutine, so anything after them never runs.
// The Go analogue of the pytest.raises dead-assertion scan.
package main

import (
	"fmt"
	"go/ast"
	"go/parser"
	"go/token"
	"os"
	"path/filepath"
	"strings"
)

// Skip is deliberately excluded: `t.Skip(...)` followed by the rest of the test
// body is the standard way to disable a test, so it is intentionally dead code,
// not a defect. Only Fatal/Fatalf/FailNow make a following statement a bug.
var enders = map[string]bool{"Fatal": true, "Fatalf": true, "FailNow": true}

func isEnder(s ast.Stmt) (string, bool) {
	es, ok := s.(*ast.ExprStmt)
	if !ok {
		return "", false
	}
	call, ok := es.X.(*ast.CallExpr)
	if !ok {
		return "", false
	}
	sel, ok := call.Fun.(*ast.SelectorExpr)
	if !ok || !enders[sel.Sel.Name] {
		return "", false
	}
	recv, ok := sel.X.(*ast.Ident)
	if !ok {
		return "", false
	}
	// Only testing.T/B receivers, conventionally named t or b.
	if recv.Name != "t" && recv.Name != "b" {
		return "", false
	}
	return recv.Name + "." + sel.Sel.Name, true
}

func main() {
	total := 0
	for _, root := range os.Args[1:] {
		filepath.Walk(root, func(path string, info os.FileInfo, err error) error {
			if err != nil || info.IsDir() || !strings.HasSuffix(path, "_test.go") {
				return nil
			}
			if strings.Contains(path, "/vendor/") || strings.Contains(path, "/testdata/") {
				return nil
			}
			fset := token.NewFileSet()
			f, err := parser.ParseFile(fset, path, nil, 0)
			if err != nil {
				return nil
			}
			ast.Inspect(f, func(n ast.Node) bool {
				var list []ast.Stmt
				switch b := n.(type) {
				case *ast.BlockStmt:
					list = b.List
				case *ast.CaseClause:
					list = b.Body
				default:
					return true
				}
				for i := 0; i < len(list)-1; i++ {
					if name, ok := isEnder(list[i]); ok {
						// A bare `return` after t.Fatal is required by the compiler,
						// which cannot know Fatal never returns. Standard idiom, not
						// a defect (go-git submodule_test.go, 2026-09-10).
						if _, isRet := list[i+1].(*ast.ReturnStmt); isRet && i+2 == len(list) {
							continue
						}
						pos := fset.Position(list[i+1].Pos())
						fmt.Printf("%s:%d  unreachable, follows %s at line %d\n",
							path, pos.Line, name, fset.Position(list[i].Pos()).Line)
						total++
						break
					}
				}
				return true
			})
			return nil
		})
	}
	fmt.Fprintf(os.Stderr, "\n%d unreachable statement(s) after a test-ending call\n", total)
}
