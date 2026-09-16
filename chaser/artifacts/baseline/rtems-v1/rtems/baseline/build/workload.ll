; ModuleID = 'workload.c'
source_filename = "workload.c"
target datalayout = "e-m:e-p270:32:32-p271:32:32-p272:64:64-i64:64-f80:128-n8:16:32:64-S128"
target triple = "x86_64-pc-linux-gnu"

@packed = internal global [8 x i8] zeroinitializer, align 4096, !dbg !0
@.str = private unnamed_addr constant [12 x i8] c"ape.analyze\00", section "llvm.metadata"
@.str.1 = private unnamed_addr constant [11 x i8] c"workload.c\00", section "llvm.metadata"
@spread = internal global [256 x i8] zeroinitializer, align 4096, !dbg !11
@conflict = internal global [32768 x i8] zeroinitializer, align 4096, !dbg !17
@llvm.global.annotations = appending global [3 x { i8*, i8*, i8*, i32, i8* }] [{ i8*, i8*, i8*, i32, i8* } { i8* bitcast (void ()* @chaser_packed to i8*), i8* getelementptr inbounds ([12 x i8], [12 x i8]* @.str, i32 0, i32 0), i8* getelementptr inbounds ([11 x i8], [11 x i8]* @.str.1, i32 0, i32 0), i32 30, i8* null }, { i8*, i8*, i8*, i32, i8* } { i8* bitcast (void ()* @chaser_spread to i8*), i8* getelementptr inbounds ([12 x i8], [12 x i8]* @.str, i32 0, i32 0), i8* getelementptr inbounds ([11 x i8], [11 x i8]* @.str.1, i32 0, i32 0), i32 31, i8* null }, { i8*, i8*, i8*, i32, i8* } { i8* bitcast (void ()* @chaser_conflict to i8*), i8* getelementptr inbounds ([12 x i8], [12 x i8]* @.str, i32 0, i32 0), i8* getelementptr inbounds ([11 x i8], [11 x i8]* @.str.1, i32 0, i32 0), i32 32, i8* null }], section "llvm.metadata"

; Function Attrs: noinline nounwind uwtable
define dso_local void @chaser_packed() #0 !dbg !33 {
  %1 = alloca i32, align 4
  %2 = alloca i32, align 4
  call void @llvm.dbg.declare(metadata i32* %1, metadata !37, metadata !DIExpression()), !dbg !40
  store i32 0, i32* %1, align 4, !dbg !40
  br label %3, !dbg !40

3:                                                ; preds = %25, %0
  %4 = load i32, i32* %1, align 4, !dbg !41
  %5 = icmp slt i32 %4, 65537, !dbg !41
  br i1 %5, label %6, label %28, !dbg !40

6:                                                ; preds = %3
  call void @llvm.dbg.declare(metadata i32* %2, metadata !43, metadata !DIExpression()), !dbg !45
  store i32 0, i32* %2, align 4, !dbg !45
  br label %7, !dbg !45

7:                                                ; preds = %21, %6
  %8 = load i32, i32* %2, align 4, !dbg !46
  %9 = icmp slt i32 %8, 8, !dbg !46
  br i1 %9, label %10, label %24, !dbg !45

10:                                               ; preds = %7
  %11 = load i32, i32* %2, align 4, !dbg !46
  %12 = sext i32 %11 to i64, !dbg !46
  %13 = getelementptr inbounds [8 x i8], [8 x i8]* @packed, i64 0, i64 %12, !dbg !46
  %14 = load volatile i8, i8* %13, align 1, !dbg !46
  %15 = zext i8 %14 to i32, !dbg !46
  %16 = add nsw i32 %15, 1, !dbg !46
  %17 = trunc i32 %16 to i8, !dbg !46
  %18 = load i32, i32* %2, align 4, !dbg !46
  %19 = sext i32 %18 to i64, !dbg !46
  %20 = getelementptr inbounds [8 x i8], [8 x i8]* @packed, i64 0, i64 %19, !dbg !46
  store volatile i8 %17, i8* %20, align 1, !dbg !46
  br label %21, !dbg !46

21:                                               ; preds = %10
  %22 = load i32, i32* %2, align 4, !dbg !46
  %23 = add nsw i32 %22, 1, !dbg !46
  store i32 %23, i32* %2, align 4, !dbg !46
  br label %7, !dbg !46, !llvm.loop !48

24:                                               ; preds = %7
  br label %25, !dbg !45

25:                                               ; preds = %24
  %26 = load i32, i32* %1, align 4, !dbg !41
  %27 = add nsw i32 %26, 1, !dbg !41
  store i32 %27, i32* %1, align 4, !dbg !41
  br label %3, !dbg !41, !llvm.loop !50

28:                                               ; preds = %3
  ret void, !dbg !51
}

; Function Attrs: nofree nosync nounwind readnone speculatable willreturn
declare void @llvm.dbg.declare(metadata, metadata, metadata) #1

; Function Attrs: noinline nounwind uwtable
define dso_local i32 @chaser_check_packed() #0 !dbg !52 {
  %1 = alloca i32, align 4
  %2 = alloca i32, align 4
  call void @llvm.dbg.declare(metadata i32* %2, metadata !55, metadata !DIExpression()), !dbg !57
  store i32 0, i32* %2, align 4, !dbg !57
  br label %3, !dbg !57

3:                                                ; preds = %16, %0
  %4 = load i32, i32* %2, align 4, !dbg !58
  %5 = icmp slt i32 %4, 8, !dbg !58
  br i1 %5, label %6, label %19, !dbg !57

6:                                                ; preds = %3
  %7 = load i32, i32* %2, align 4, !dbg !60
  %8 = mul nsw i32 %7, 1, !dbg !60
  %9 = sext i32 %8 to i64, !dbg !60
  %10 = getelementptr inbounds [8 x i8], [8 x i8]* @packed, i64 0, i64 %9, !dbg !60
  %11 = load volatile i8, i8* %10, align 1, !dbg !60
  %12 = zext i8 %11 to i32, !dbg !60
  %13 = icmp ne i32 %12, 1, !dbg !60
  br i1 %13, label %14, label %15, !dbg !58

14:                                               ; preds = %6
  store i32 0, i32* %1, align 4, !dbg !60
  br label %20, !dbg !60

15:                                               ; preds = %6
  br label %16, !dbg !60

16:                                               ; preds = %15
  %17 = load i32, i32* %2, align 4, !dbg !58
  %18 = add nsw i32 %17, 1, !dbg !58
  store i32 %18, i32* %2, align 4, !dbg !58
  br label %3, !dbg !58, !llvm.loop !62

19:                                               ; preds = %3
  store i32 1, i32* %1, align 4, !dbg !63
  br label %20, !dbg !63

20:                                               ; preds = %19, %14
  %21 = load i32, i32* %1, align 4, !dbg !63
  ret i32 %21, !dbg !63
}

; Function Attrs: noinline nounwind uwtable
define dso_local void @chaser_spread() #0 !dbg !64 {
  %1 = alloca i32, align 4
  %2 = alloca i32, align 4
  call void @llvm.dbg.declare(metadata i32* %1, metadata !65, metadata !DIExpression()), !dbg !67
  store i32 0, i32* %1, align 4, !dbg !67
  br label %3, !dbg !67

3:                                                ; preds = %25, %0
  %4 = load i32, i32* %1, align 4, !dbg !68
  %5 = icmp slt i32 %4, 65537, !dbg !68
  br i1 %5, label %6, label %28, !dbg !67

6:                                                ; preds = %3
  call void @llvm.dbg.declare(metadata i32* %2, metadata !70, metadata !DIExpression()), !dbg !72
  store i32 0, i32* %2, align 4, !dbg !72
  br label %7, !dbg !72

7:                                                ; preds = %21, %6
  %8 = load i32, i32* %2, align 4, !dbg !73
  %9 = icmp slt i32 %8, 256, !dbg !73
  br i1 %9, label %10, label %24, !dbg !72

10:                                               ; preds = %7
  %11 = load i32, i32* %2, align 4, !dbg !73
  %12 = sext i32 %11 to i64, !dbg !73
  %13 = getelementptr inbounds [256 x i8], [256 x i8]* @spread, i64 0, i64 %12, !dbg !73
  %14 = load volatile i8, i8* %13, align 1, !dbg !73
  %15 = zext i8 %14 to i32, !dbg !73
  %16 = add nsw i32 %15, 1, !dbg !73
  %17 = trunc i32 %16 to i8, !dbg !73
  %18 = load i32, i32* %2, align 4, !dbg !73
  %19 = sext i32 %18 to i64, !dbg !73
  %20 = getelementptr inbounds [256 x i8], [256 x i8]* @spread, i64 0, i64 %19, !dbg !73
  store volatile i8 %17, i8* %20, align 1, !dbg !73
  br label %21, !dbg !73

21:                                               ; preds = %10
  %22 = load i32, i32* %2, align 4, !dbg !73
  %23 = add nsw i32 %22, 32, !dbg !73
  store i32 %23, i32* %2, align 4, !dbg !73
  br label %7, !dbg !73, !llvm.loop !75

24:                                               ; preds = %7
  br label %25, !dbg !72

25:                                               ; preds = %24
  %26 = load i32, i32* %1, align 4, !dbg !68
  %27 = add nsw i32 %26, 1, !dbg !68
  store i32 %27, i32* %1, align 4, !dbg !68
  br label %3, !dbg !68, !llvm.loop !76

28:                                               ; preds = %3
  ret void, !dbg !77
}

; Function Attrs: noinline nounwind uwtable
define dso_local i32 @chaser_check_spread() #0 !dbg !78 {
  %1 = alloca i32, align 4
  %2 = alloca i32, align 4
  call void @llvm.dbg.declare(metadata i32* %2, metadata !79, metadata !DIExpression()), !dbg !81
  store i32 0, i32* %2, align 4, !dbg !81
  br label %3, !dbg !81

3:                                                ; preds = %16, %0
  %4 = load i32, i32* %2, align 4, !dbg !82
  %5 = icmp slt i32 %4, 8, !dbg !82
  br i1 %5, label %6, label %19, !dbg !81

6:                                                ; preds = %3
  %7 = load i32, i32* %2, align 4, !dbg !84
  %8 = mul nsw i32 %7, 32, !dbg !84
  %9 = sext i32 %8 to i64, !dbg !84
  %10 = getelementptr inbounds [256 x i8], [256 x i8]* @spread, i64 0, i64 %9, !dbg !84
  %11 = load volatile i8, i8* %10, align 1, !dbg !84
  %12 = zext i8 %11 to i32, !dbg !84
  %13 = icmp ne i32 %12, 1, !dbg !84
  br i1 %13, label %14, label %15, !dbg !82

14:                                               ; preds = %6
  store i32 0, i32* %1, align 4, !dbg !84
  br label %20, !dbg !84

15:                                               ; preds = %6
  br label %16, !dbg !84

16:                                               ; preds = %15
  %17 = load i32, i32* %2, align 4, !dbg !82
  %18 = add nsw i32 %17, 1, !dbg !82
  store i32 %18, i32* %2, align 4, !dbg !82
  br label %3, !dbg !82, !llvm.loop !86

19:                                               ; preds = %3
  store i32 1, i32* %1, align 4, !dbg !87
  br label %20, !dbg !87

20:                                               ; preds = %19, %14
  %21 = load i32, i32* %1, align 4, !dbg !87
  ret i32 %21, !dbg !87
}

; Function Attrs: noinline nounwind uwtable
define dso_local void @chaser_conflict() #0 !dbg !88 {
  %1 = alloca i32, align 4
  %2 = alloca i32, align 4
  call void @llvm.dbg.declare(metadata i32* %1, metadata !89, metadata !DIExpression()), !dbg !91
  store i32 0, i32* %1, align 4, !dbg !91
  br label %3, !dbg !91

3:                                                ; preds = %25, %0
  %4 = load i32, i32* %1, align 4, !dbg !92
  %5 = icmp slt i32 %4, 65537, !dbg !92
  br i1 %5, label %6, label %28, !dbg !91

6:                                                ; preds = %3
  call void @llvm.dbg.declare(metadata i32* %2, metadata !94, metadata !DIExpression()), !dbg !96
  store i32 0, i32* %2, align 4, !dbg !96
  br label %7, !dbg !96

7:                                                ; preds = %21, %6
  %8 = load i32, i32* %2, align 4, !dbg !97
  %9 = icmp slt i32 %8, 32768, !dbg !97
  br i1 %9, label %10, label %24, !dbg !96

10:                                               ; preds = %7
  %11 = load i32, i32* %2, align 4, !dbg !97
  %12 = sext i32 %11 to i64, !dbg !97
  %13 = getelementptr inbounds [32768 x i8], [32768 x i8]* @conflict, i64 0, i64 %12, !dbg !97
  %14 = load volatile i8, i8* %13, align 1, !dbg !97
  %15 = zext i8 %14 to i32, !dbg !97
  %16 = add nsw i32 %15, 1, !dbg !97
  %17 = trunc i32 %16 to i8, !dbg !97
  %18 = load i32, i32* %2, align 4, !dbg !97
  %19 = sext i32 %18 to i64, !dbg !97
  %20 = getelementptr inbounds [32768 x i8], [32768 x i8]* @conflict, i64 0, i64 %19, !dbg !97
  store volatile i8 %17, i8* %20, align 1, !dbg !97
  br label %21, !dbg !97

21:                                               ; preds = %10
  %22 = load i32, i32* %2, align 4, !dbg !97
  %23 = add nsw i32 %22, 4096, !dbg !97
  store i32 %23, i32* %2, align 4, !dbg !97
  br label %7, !dbg !97, !llvm.loop !99

24:                                               ; preds = %7
  br label %25, !dbg !96

25:                                               ; preds = %24
  %26 = load i32, i32* %1, align 4, !dbg !92
  %27 = add nsw i32 %26, 1, !dbg !92
  store i32 %27, i32* %1, align 4, !dbg !92
  br label %3, !dbg !92, !llvm.loop !100

28:                                               ; preds = %3
  ret void, !dbg !101
}

; Function Attrs: noinline nounwind uwtable
define dso_local i32 @chaser_check_conflict() #0 !dbg !102 {
  %1 = alloca i32, align 4
  %2 = alloca i32, align 4
  call void @llvm.dbg.declare(metadata i32* %2, metadata !103, metadata !DIExpression()), !dbg !105
  store i32 0, i32* %2, align 4, !dbg !105
  br label %3, !dbg !105

3:                                                ; preds = %16, %0
  %4 = load i32, i32* %2, align 4, !dbg !106
  %5 = icmp slt i32 %4, 8, !dbg !106
  br i1 %5, label %6, label %19, !dbg !105

6:                                                ; preds = %3
  %7 = load i32, i32* %2, align 4, !dbg !108
  %8 = mul nsw i32 %7, 4096, !dbg !108
  %9 = sext i32 %8 to i64, !dbg !108
  %10 = getelementptr inbounds [32768 x i8], [32768 x i8]* @conflict, i64 0, i64 %9, !dbg !108
  %11 = load volatile i8, i8* %10, align 1, !dbg !108
  %12 = zext i8 %11 to i32, !dbg !108
  %13 = icmp ne i32 %12, 1, !dbg !108
  br i1 %13, label %14, label %15, !dbg !106

14:                                               ; preds = %6
  store i32 0, i32* %1, align 4, !dbg !108
  br label %20, !dbg !108

15:                                               ; preds = %6
  br label %16, !dbg !108

16:                                               ; preds = %15
  %17 = load i32, i32* %2, align 4, !dbg !106
  %18 = add nsw i32 %17, 1, !dbg !106
  store i32 %18, i32* %2, align 4, !dbg !106
  br label %3, !dbg !106, !llvm.loop !110

19:                                               ; preds = %3
  store i32 1, i32* %1, align 4, !dbg !111
  br label %20, !dbg !111

20:                                               ; preds = %19, %14
  %21 = load i32, i32* %1, align 4, !dbg !111
  ret i32 %21, !dbg !111
}

attributes #0 = { noinline nounwind uwtable "frame-pointer"="all" "min-legal-vector-width"="0" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #1 = { nofree nosync nounwind readnone speculatable willreturn }

!llvm.dbg.cu = !{!2}
!llvm.module.flags = !{!25, !26, !27, !28, !29, !30, !31}
!llvm.ident = !{!32}

!0 = !DIGlobalVariableExpression(var: !1, expr: !DIExpression())
!1 = distinct !DIGlobalVariable(name: "packed", scope: !2, file: !3, line: 10, type: !22, isLocal: true, isDefinition: true, align: 32768)
!2 = distinct !DICompileUnit(language: DW_LANG_C99, file: !3, producer: "Ubuntu clang version 14.0.0-1ubuntu1.1", isOptimized: false, runtimeVersion: 0, emissionKind: FullDebug, retainedTypes: !4, globals: !10, splitDebugInlining: false, nameTableKind: None)
!3 = !DIFile(filename: "workload.c", directory: "/workspace/experiments/chaser/rtems/baseline", checksumkind: CSK_MD5, checksum: "5d5d6cd3416efd4a9f110231e8be534a")
!4 = !{!5}
!5 = !DIDerivedType(tag: DW_TAG_typedef, name: "uint8_t", file: !6, line: 24, baseType: !7)
!6 = !DIFile(filename: "/usr/include/x86_64-linux-gnu/bits/stdint-uintn.h", directory: "", checksumkind: CSK_MD5, checksum: "2bf2ae53c58c01b1a1b9383b5195125c")
!7 = !DIDerivedType(tag: DW_TAG_typedef, name: "__uint8_t", file: !8, line: 38, baseType: !9)
!8 = !DIFile(filename: "/usr/include/x86_64-linux-gnu/bits/types.h", directory: "", checksumkind: CSK_MD5, checksum: "d108b5f93a74c50510d7d9bc0ab36df9")
!9 = !DIBasicType(name: "unsigned char", size: 8, encoding: DW_ATE_unsigned_char)
!10 = !{!0, !11, !17}
!11 = !DIGlobalVariableExpression(var: !12, expr: !DIExpression())
!12 = distinct !DIGlobalVariable(name: "spread", scope: !2, file: !3, line: 11, type: !13, isLocal: true, isDefinition: true, align: 32768)
!13 = !DICompositeType(tag: DW_TAG_array_type, baseType: !14, size: 2048, elements: !15)
!14 = !DIDerivedType(tag: DW_TAG_volatile_type, baseType: !5)
!15 = !{!16}
!16 = !DISubrange(count: 256)
!17 = !DIGlobalVariableExpression(var: !18, expr: !DIExpression())
!18 = distinct !DIGlobalVariable(name: "conflict", scope: !2, file: !3, line: 12, type: !19, isLocal: true, isDefinition: true, align: 32768)
!19 = !DICompositeType(tag: DW_TAG_array_type, baseType: !14, size: 262144, elements: !20)
!20 = !{!21}
!21 = !DISubrange(count: 32768)
!22 = !DICompositeType(tag: DW_TAG_array_type, baseType: !14, size: 64, elements: !23)
!23 = !{!24}
!24 = !DISubrange(count: 8)
!25 = !{i32 7, !"Dwarf Version", i32 5}
!26 = !{i32 2, !"Debug Info Version", i32 3}
!27 = !{i32 1, !"wchar_size", i32 4}
!28 = !{i32 7, !"PIC Level", i32 2}
!29 = !{i32 7, !"PIE Level", i32 2}
!30 = !{i32 7, !"uwtable", i32 1}
!31 = !{i32 7, !"frame-pointer", i32 2}
!32 = !{!"Ubuntu clang version 14.0.0-1ubuntu1.1"}
!33 = distinct !DISubprogram(name: "chaser_packed", scope: !3, file: !3, line: 30, type: !34, scopeLine: 30, flags: DIFlagPrototyped, spFlags: DISPFlagDefinition, unit: !2, retainedNodes: !36)
!34 = !DISubroutineType(types: !35)
!35 = !{null}
!36 = !{}
!37 = !DILocalVariable(name: "sweep", scope: !38, file: !3, line: 30, type: !39)
!38 = distinct !DILexicalBlock(scope: !33, file: !3, line: 30, column: 1)
!39 = !DIBasicType(name: "int", size: 32, encoding: DW_ATE_signed)
!40 = !DILocation(line: 30, column: 1, scope: !38)
!41 = !DILocation(line: 30, column: 1, scope: !42)
!42 = distinct !DILexicalBlock(scope: !38, file: !3, line: 30, column: 1)
!43 = !DILocalVariable(name: "i", scope: !44, file: !3, line: 30, type: !39)
!44 = distinct !DILexicalBlock(scope: !42, file: !3, line: 30, column: 1)
!45 = !DILocation(line: 30, column: 1, scope: !44)
!46 = !DILocation(line: 30, column: 1, scope: !47)
!47 = distinct !DILexicalBlock(scope: !44, file: !3, line: 30, column: 1)
!48 = distinct !{!48, !45, !45, !49}
!49 = !{!"llvm.loop.mustprogress"}
!50 = distinct !{!50, !40, !40, !49}
!51 = !DILocation(line: 30, column: 1, scope: !33)
!52 = distinct !DISubprogram(name: "chaser_check_packed", scope: !3, file: !3, line: 30, type: !53, scopeLine: 30, flags: DIFlagPrototyped, spFlags: DISPFlagDefinition, unit: !2, retainedNodes: !36)
!53 = !DISubroutineType(types: !54)
!54 = !{!39}
!55 = !DILocalVariable(name: "i", scope: !56, file: !3, line: 30, type: !39)
!56 = distinct !DILexicalBlock(scope: !52, file: !3, line: 30, column: 1)
!57 = !DILocation(line: 30, column: 1, scope: !56)
!58 = !DILocation(line: 30, column: 1, scope: !59)
!59 = distinct !DILexicalBlock(scope: !56, file: !3, line: 30, column: 1)
!60 = !DILocation(line: 30, column: 1, scope: !61)
!61 = distinct !DILexicalBlock(scope: !59, file: !3, line: 30, column: 1)
!62 = distinct !{!62, !57, !57, !49}
!63 = !DILocation(line: 30, column: 1, scope: !52)
!64 = distinct !DISubprogram(name: "chaser_spread", scope: !3, file: !3, line: 31, type: !34, scopeLine: 31, flags: DIFlagPrototyped, spFlags: DISPFlagDefinition, unit: !2, retainedNodes: !36)
!65 = !DILocalVariable(name: "sweep", scope: !66, file: !3, line: 31, type: !39)
!66 = distinct !DILexicalBlock(scope: !64, file: !3, line: 31, column: 1)
!67 = !DILocation(line: 31, column: 1, scope: !66)
!68 = !DILocation(line: 31, column: 1, scope: !69)
!69 = distinct !DILexicalBlock(scope: !66, file: !3, line: 31, column: 1)
!70 = !DILocalVariable(name: "i", scope: !71, file: !3, line: 31, type: !39)
!71 = distinct !DILexicalBlock(scope: !69, file: !3, line: 31, column: 1)
!72 = !DILocation(line: 31, column: 1, scope: !71)
!73 = !DILocation(line: 31, column: 1, scope: !74)
!74 = distinct !DILexicalBlock(scope: !71, file: !3, line: 31, column: 1)
!75 = distinct !{!75, !72, !72, !49}
!76 = distinct !{!76, !67, !67, !49}
!77 = !DILocation(line: 31, column: 1, scope: !64)
!78 = distinct !DISubprogram(name: "chaser_check_spread", scope: !3, file: !3, line: 31, type: !53, scopeLine: 31, flags: DIFlagPrototyped, spFlags: DISPFlagDefinition, unit: !2, retainedNodes: !36)
!79 = !DILocalVariable(name: "i", scope: !80, file: !3, line: 31, type: !39)
!80 = distinct !DILexicalBlock(scope: !78, file: !3, line: 31, column: 1)
!81 = !DILocation(line: 31, column: 1, scope: !80)
!82 = !DILocation(line: 31, column: 1, scope: !83)
!83 = distinct !DILexicalBlock(scope: !80, file: !3, line: 31, column: 1)
!84 = !DILocation(line: 31, column: 1, scope: !85)
!85 = distinct !DILexicalBlock(scope: !83, file: !3, line: 31, column: 1)
!86 = distinct !{!86, !81, !81, !49}
!87 = !DILocation(line: 31, column: 1, scope: !78)
!88 = distinct !DISubprogram(name: "chaser_conflict", scope: !3, file: !3, line: 32, type: !34, scopeLine: 32, flags: DIFlagPrototyped, spFlags: DISPFlagDefinition, unit: !2, retainedNodes: !36)
!89 = !DILocalVariable(name: "sweep", scope: !90, file: !3, line: 32, type: !39)
!90 = distinct !DILexicalBlock(scope: !88, file: !3, line: 32, column: 1)
!91 = !DILocation(line: 32, column: 1, scope: !90)
!92 = !DILocation(line: 32, column: 1, scope: !93)
!93 = distinct !DILexicalBlock(scope: !90, file: !3, line: 32, column: 1)
!94 = !DILocalVariable(name: "i", scope: !95, file: !3, line: 32, type: !39)
!95 = distinct !DILexicalBlock(scope: !93, file: !3, line: 32, column: 1)
!96 = !DILocation(line: 32, column: 1, scope: !95)
!97 = !DILocation(line: 32, column: 1, scope: !98)
!98 = distinct !DILexicalBlock(scope: !95, file: !3, line: 32, column: 1)
!99 = distinct !{!99, !96, !96, !49}
!100 = distinct !{!100, !91, !91, !49}
!101 = !DILocation(line: 32, column: 1, scope: !88)
!102 = distinct !DISubprogram(name: "chaser_check_conflict", scope: !3, file: !3, line: 32, type: !53, scopeLine: 32, flags: DIFlagPrototyped, spFlags: DISPFlagDefinition, unit: !2, retainedNodes: !36)
!103 = !DILocalVariable(name: "i", scope: !104, file: !3, line: 32, type: !39)
!104 = distinct !DILexicalBlock(scope: !102, file: !3, line: 32, column: 1)
!105 = !DILocation(line: 32, column: 1, scope: !104)
!106 = !DILocation(line: 32, column: 1, scope: !107)
!107 = distinct !DILexicalBlock(scope: !104, file: !3, line: 32, column: 1)
!108 = !DILocation(line: 32, column: 1, scope: !109)
!109 = distinct !DILexicalBlock(scope: !107, file: !3, line: 32, column: 1)
!110 = distinct !{!110, !105, !105, !49}
!111 = !DILocation(line: 32, column: 1, scope: !102)
