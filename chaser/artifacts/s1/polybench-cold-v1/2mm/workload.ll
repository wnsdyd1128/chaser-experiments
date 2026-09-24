; ModuleID = '/tmp/chaser-polybench-run-v1/2mm/workload.c'
source_filename = "/tmp/chaser-polybench-run-v1/2mm/workload.c"
target datalayout = "e-m:e-p270:32:32-p271:32:32-p272:64:64-i64:64-f80:128-n8:16:32:64-S128"
target triple = "x86_64-pc-linux-gnu"

@tmp = dso_local global [16 x [18 x double]] zeroinitializer, align 16, !dbg !0
@A = dso_local global [16 x [20 x double]] zeroinitializer, align 16, !dbg !7
@B = dso_local global [20 x [18 x double]] zeroinitializer, align 16, !dbg !15
@D = dso_local global [16 x [22 x double]] zeroinitializer, align 16, !dbg !25
@C = dso_local global [18 x [22 x double]] zeroinitializer, align 16, !dbg !20
@.str = private unnamed_addr constant [12 x i8] c"ape.analyze\00", section "llvm.metadata"
@.str.1 = private unnamed_addr constant [44 x i8] c"/tmp/chaser-polybench-run-v1/2mm/workload.c\00", section "llvm.metadata"
@.str.2 = private unnamed_addr constant [16 x i8] c"checksum=%.17g\0A\00", align 1
@llvm.global.annotations = appending global [1 x { i8*, i8*, i8*, i32, i8* }] [{ i8*, i8*, i8*, i32, i8* } { i8* bitcast (void (double, double)* @kernel_2mm to i8*), i8* getelementptr inbounds ([12 x i8], [12 x i8]* @.str, i32 0, i32 0), i8* getelementptr inbounds ([44 x i8], [44 x i8]* @.str.1, i32 0, i32 0), i32 26, i8* null }], section "llvm.metadata"

; Function Attrs: noinline nounwind uwtable
define dso_local void @kernel_2mm(double noundef %0, double noundef %1) #0 !dbg !39 {
  %3 = alloca double, align 8
  %4 = alloca double, align 8
  %5 = alloca i32, align 4
  %6 = alloca i32, align 4
  %7 = alloca i32, align 4
  store double %0, double* %3, align 8
  call void @llvm.dbg.declare(metadata double* %3, metadata !43, metadata !DIExpression()), !dbg !44
  store double %1, double* %4, align 8
  call void @llvm.dbg.declare(metadata double* %4, metadata !45, metadata !DIExpression()), !dbg !46
  call void @llvm.dbg.declare(metadata i32* %5, metadata !47, metadata !DIExpression()), !dbg !49
  call void @llvm.dbg.declare(metadata i32* %6, metadata !50, metadata !DIExpression()), !dbg !51
  call void @llvm.dbg.declare(metadata i32* %7, metadata !52, metadata !DIExpression()), !dbg !53
  store i32 0, i32* %5, align 4, !dbg !54
  br label %8, !dbg !56

8:                                                ; preds = %58, %2
  %9 = load i32, i32* %5, align 4, !dbg !57
  %10 = icmp slt i32 %9, 16, !dbg !59
  br i1 %10, label %11, label %61, !dbg !60

11:                                               ; preds = %8
  store i32 0, i32* %6, align 4, !dbg !61
  br label %12, !dbg !64

12:                                               ; preds = %54, %11
  %13 = load i32, i32* %6, align 4, !dbg !65
  %14 = icmp slt i32 %13, 18, !dbg !67
  br i1 %14, label %15, label %57, !dbg !68

15:                                               ; preds = %12
  %16 = load i32, i32* %5, align 4, !dbg !69
  %17 = sext i32 %16 to i64, !dbg !71
  %18 = getelementptr inbounds [16 x [18 x double]], [16 x [18 x double]]* @tmp, i64 0, i64 %17, !dbg !71
  %19 = load i32, i32* %6, align 4, !dbg !72
  %20 = sext i32 %19 to i64, !dbg !71
  %21 = getelementptr inbounds [18 x double], [18 x double]* %18, i64 0, i64 %20, !dbg !71
  store volatile double 0.000000e+00, double* %21, align 8, !dbg !73
  store i32 0, i32* %7, align 4, !dbg !74
  br label %22, !dbg !76

22:                                               ; preds = %50, %15
  %23 = load i32, i32* %7, align 4, !dbg !77
  %24 = icmp slt i32 %23, 20, !dbg !79
  br i1 %24, label %25, label %53, !dbg !80

25:                                               ; preds = %22
  %26 = load double, double* %3, align 8, !dbg !81
  %27 = load i32, i32* %5, align 4, !dbg !83
  %28 = sext i32 %27 to i64, !dbg !84
  %29 = getelementptr inbounds [16 x [20 x double]], [16 x [20 x double]]* @A, i64 0, i64 %28, !dbg !84
  %30 = load i32, i32* %7, align 4, !dbg !85
  %31 = sext i32 %30 to i64, !dbg !84
  %32 = getelementptr inbounds [20 x double], [20 x double]* %29, i64 0, i64 %31, !dbg !84
  %33 = load volatile double, double* %32, align 8, !dbg !84
  %34 = fmul double %26, %33, !dbg !86
  %35 = load i32, i32* %7, align 4, !dbg !87
  %36 = sext i32 %35 to i64, !dbg !88
  %37 = getelementptr inbounds [20 x [18 x double]], [20 x [18 x double]]* @B, i64 0, i64 %36, !dbg !88
  %38 = load i32, i32* %6, align 4, !dbg !89
  %39 = sext i32 %38 to i64, !dbg !88
  %40 = getelementptr inbounds [18 x double], [18 x double]* %37, i64 0, i64 %39, !dbg !88
  %41 = load volatile double, double* %40, align 8, !dbg !88
  %42 = load i32, i32* %5, align 4, !dbg !90
  %43 = sext i32 %42 to i64, !dbg !91
  %44 = getelementptr inbounds [16 x [18 x double]], [16 x [18 x double]]* @tmp, i64 0, i64 %43, !dbg !91
  %45 = load i32, i32* %6, align 4, !dbg !92
  %46 = sext i32 %45 to i64, !dbg !91
  %47 = getelementptr inbounds [18 x double], [18 x double]* %44, i64 0, i64 %46, !dbg !91
  %48 = load volatile double, double* %47, align 8, !dbg !93
  %49 = call double @llvm.fmuladd.f64(double %34, double %41, double %48), !dbg !93
  store volatile double %49, double* %47, align 8, !dbg !93
  br label %50, !dbg !94

50:                                               ; preds = %25
  %51 = load i32, i32* %7, align 4, !dbg !95
  %52 = add nsw i32 %51, 1, !dbg !95
  store i32 %52, i32* %7, align 4, !dbg !95
  br label %22, !dbg !96, !llvm.loop !97

53:                                               ; preds = %22
  br label %54, !dbg !100

54:                                               ; preds = %53
  %55 = load i32, i32* %6, align 4, !dbg !101
  %56 = add nsw i32 %55, 1, !dbg !101
  store i32 %56, i32* %6, align 4, !dbg !101
  br label %12, !dbg !102, !llvm.loop !103

57:                                               ; preds = %12
  br label %58, !dbg !105

58:                                               ; preds = %57
  %59 = load i32, i32* %5, align 4, !dbg !106
  %60 = add nsw i32 %59, 1, !dbg !106
  store i32 %60, i32* %5, align 4, !dbg !106
  br label %8, !dbg !107, !llvm.loop !108

61:                                               ; preds = %8
  store i32 0, i32* %5, align 4, !dbg !110
  br label %62, !dbg !112

62:                                               ; preds = %112, %61
  %63 = load i32, i32* %5, align 4, !dbg !113
  %64 = icmp slt i32 %63, 16, !dbg !115
  br i1 %64, label %65, label %115, !dbg !116

65:                                               ; preds = %62
  store i32 0, i32* %6, align 4, !dbg !117
  br label %66, !dbg !120

66:                                               ; preds = %108, %65
  %67 = load i32, i32* %6, align 4, !dbg !121
  %68 = icmp slt i32 %67, 22, !dbg !123
  br i1 %68, label %69, label %111, !dbg !124

69:                                               ; preds = %66
  %70 = load i32, i32* %5, align 4, !dbg !125
  %71 = sext i32 %70 to i64, !dbg !127
  %72 = getelementptr inbounds [16 x [22 x double]], [16 x [22 x double]]* @D, i64 0, i64 %71, !dbg !127
  %73 = load i32, i32* %6, align 4, !dbg !128
  %74 = sext i32 %73 to i64, !dbg !127
  %75 = getelementptr inbounds [22 x double], [22 x double]* %72, i64 0, i64 %74, !dbg !127
  store volatile double 0.000000e+00, double* %75, align 8, !dbg !129
  store i32 0, i32* %7, align 4, !dbg !130
  br label %76, !dbg !132

76:                                               ; preds = %104, %69
  %77 = load i32, i32* %7, align 4, !dbg !133
  %78 = icmp slt i32 %77, 18, !dbg !135
  br i1 %78, label %79, label %107, !dbg !136

79:                                               ; preds = %76
  %80 = load double, double* %4, align 8, !dbg !137
  %81 = load i32, i32* %5, align 4, !dbg !139
  %82 = sext i32 %81 to i64, !dbg !140
  %83 = getelementptr inbounds [16 x [18 x double]], [16 x [18 x double]]* @tmp, i64 0, i64 %82, !dbg !140
  %84 = load i32, i32* %7, align 4, !dbg !141
  %85 = sext i32 %84 to i64, !dbg !140
  %86 = getelementptr inbounds [18 x double], [18 x double]* %83, i64 0, i64 %85, !dbg !140
  %87 = load volatile double, double* %86, align 8, !dbg !140
  %88 = fmul double %80, %87, !dbg !142
  %89 = load i32, i32* %7, align 4, !dbg !143
  %90 = sext i32 %89 to i64, !dbg !144
  %91 = getelementptr inbounds [18 x [22 x double]], [18 x [22 x double]]* @C, i64 0, i64 %90, !dbg !144
  %92 = load i32, i32* %6, align 4, !dbg !145
  %93 = sext i32 %92 to i64, !dbg !144
  %94 = getelementptr inbounds [22 x double], [22 x double]* %91, i64 0, i64 %93, !dbg !144
  %95 = load volatile double, double* %94, align 8, !dbg !144
  %96 = load i32, i32* %5, align 4, !dbg !146
  %97 = sext i32 %96 to i64, !dbg !147
  %98 = getelementptr inbounds [16 x [22 x double]], [16 x [22 x double]]* @D, i64 0, i64 %97, !dbg !147
  %99 = load i32, i32* %6, align 4, !dbg !148
  %100 = sext i32 %99 to i64, !dbg !147
  %101 = getelementptr inbounds [22 x double], [22 x double]* %98, i64 0, i64 %100, !dbg !147
  %102 = load volatile double, double* %101, align 8, !dbg !149
  %103 = call double @llvm.fmuladd.f64(double %88, double %95, double %102), !dbg !149
  store volatile double %103, double* %101, align 8, !dbg !149
  br label %104, !dbg !150

104:                                              ; preds = %79
  %105 = load i32, i32* %7, align 4, !dbg !151
  %106 = add nsw i32 %105, 1, !dbg !151
  store i32 %106, i32* %7, align 4, !dbg !151
  br label %76, !dbg !152, !llvm.loop !153

107:                                              ; preds = %76
  br label %108, !dbg !155

108:                                              ; preds = %107
  %109 = load i32, i32* %6, align 4, !dbg !156
  %110 = add nsw i32 %109, 1, !dbg !156
  store i32 %110, i32* %6, align 4, !dbg !156
  br label %66, !dbg !157, !llvm.loop !158

111:                                              ; preds = %66
  br label %112, !dbg !160

112:                                              ; preds = %111
  %113 = load i32, i32* %5, align 4, !dbg !161
  %114 = add nsw i32 %113, 1, !dbg !161
  store i32 %114, i32* %5, align 4, !dbg !161
  br label %62, !dbg !162, !llvm.loop !163

115:                                              ; preds = %62
  ret void, !dbg !165
}

; Function Attrs: nofree nosync nounwind readnone speculatable willreturn
declare void @llvm.dbg.declare(metadata, metadata, metadata) #1

; Function Attrs: nofree nosync nounwind readnone speculatable willreturn
declare double @llvm.fmuladd.f64(double, double, double) #1

; Function Attrs: noinline nounwind uwtable
define dso_local i32 @main() #0 !dbg !166 {
  %1 = alloca i32, align 4
  %2 = alloca i32, align 4
  %3 = alloca i32, align 4
  %4 = alloca double, align 8
  %5 = alloca i32, align 4
  %6 = alloca i32, align 4
  store i32 0, i32* %1, align 4
  call void @llvm.dbg.declare(metadata i32* %2, metadata !169, metadata !DIExpression()), !dbg !170
  call void @llvm.dbg.declare(metadata i32* %3, metadata !171, metadata !DIExpression()), !dbg !172
  store i32 0, i32* %2, align 4, !dbg !173
  br label %7, !dbg !175

7:                                                ; preds = %30, %0
  %8 = load i32, i32* %2, align 4, !dbg !176
  %9 = icmp slt i32 %8, 16, !dbg !178
  br i1 %9, label %10, label %33, !dbg !179

10:                                               ; preds = %7
  store i32 0, i32* %3, align 4, !dbg !180
  br label %11, !dbg !183

11:                                               ; preds = %26, %10
  %12 = load i32, i32* %3, align 4, !dbg !184
  %13 = icmp slt i32 %12, 20, !dbg !186
  br i1 %13, label %14, label %29, !dbg !187

14:                                               ; preds = %11
  %15 = load i32, i32* %2, align 4, !dbg !188
  %16 = load i32, i32* %3, align 4, !dbg !190
  %17 = mul nsw i32 %15, %16, !dbg !191
  %18 = sitofp i32 %17 to double, !dbg !192
  %19 = fdiv double %18, 1.600000e+01, !dbg !193
  %20 = load i32, i32* %2, align 4, !dbg !194
  %21 = sext i32 %20 to i64, !dbg !195
  %22 = getelementptr inbounds [16 x [20 x double]], [16 x [20 x double]]* @A, i64 0, i64 %21, !dbg !195
  %23 = load i32, i32* %3, align 4, !dbg !196
  %24 = sext i32 %23 to i64, !dbg !195
  %25 = getelementptr inbounds [20 x double], [20 x double]* %22, i64 0, i64 %24, !dbg !195
  store volatile double %19, double* %25, align 8, !dbg !197
  br label %26, !dbg !198

26:                                               ; preds = %14
  %27 = load i32, i32* %3, align 4, !dbg !199
  %28 = add nsw i32 %27, 1, !dbg !199
  store i32 %28, i32* %3, align 4, !dbg !199
  br label %11, !dbg !200, !llvm.loop !201

29:                                               ; preds = %11
  br label %30, !dbg !203

30:                                               ; preds = %29
  %31 = load i32, i32* %2, align 4, !dbg !204
  %32 = add nsw i32 %31, 1, !dbg !204
  store i32 %32, i32* %2, align 4, !dbg !204
  br label %7, !dbg !205, !llvm.loop !206

33:                                               ; preds = %7
  store i32 0, i32* %2, align 4, !dbg !208
  br label %34, !dbg !210

34:                                               ; preds = %58, %33
  %35 = load i32, i32* %2, align 4, !dbg !211
  %36 = icmp slt i32 %35, 20, !dbg !213
  br i1 %36, label %37, label %61, !dbg !214

37:                                               ; preds = %34
  store i32 0, i32* %3, align 4, !dbg !215
  br label %38, !dbg !218

38:                                               ; preds = %54, %37
  %39 = load i32, i32* %3, align 4, !dbg !219
  %40 = icmp slt i32 %39, 18, !dbg !221
  br i1 %40, label %41, label %57, !dbg !222

41:                                               ; preds = %38
  %42 = load i32, i32* %2, align 4, !dbg !223
  %43 = load i32, i32* %3, align 4, !dbg !225
  %44 = add nsw i32 %43, 1, !dbg !226
  %45 = mul nsw i32 %42, %44, !dbg !227
  %46 = sitofp i32 %45 to double, !dbg !228
  %47 = fdiv double %46, 1.800000e+01, !dbg !229
  %48 = load i32, i32* %2, align 4, !dbg !230
  %49 = sext i32 %48 to i64, !dbg !231
  %50 = getelementptr inbounds [20 x [18 x double]], [20 x [18 x double]]* @B, i64 0, i64 %49, !dbg !231
  %51 = load i32, i32* %3, align 4, !dbg !232
  %52 = sext i32 %51 to i64, !dbg !231
  %53 = getelementptr inbounds [18 x double], [18 x double]* %50, i64 0, i64 %52, !dbg !231
  store volatile double %47, double* %53, align 8, !dbg !233
  br label %54, !dbg !234

54:                                               ; preds = %41
  %55 = load i32, i32* %3, align 4, !dbg !235
  %56 = add nsw i32 %55, 1, !dbg !235
  store i32 %56, i32* %3, align 4, !dbg !235
  br label %38, !dbg !236, !llvm.loop !237

57:                                               ; preds = %38
  br label %58, !dbg !239

58:                                               ; preds = %57
  %59 = load i32, i32* %2, align 4, !dbg !240
  %60 = add nsw i32 %59, 1, !dbg !240
  store i32 %60, i32* %2, align 4, !dbg !240
  br label %34, !dbg !241, !llvm.loop !242

61:                                               ; preds = %34
  store i32 0, i32* %2, align 4, !dbg !244
  br label %62, !dbg !246

62:                                               ; preds = %86, %61
  %63 = load i32, i32* %2, align 4, !dbg !247
  %64 = icmp slt i32 %63, 18, !dbg !249
  br i1 %64, label %65, label %89, !dbg !250

65:                                               ; preds = %62
  store i32 0, i32* %3, align 4, !dbg !251
  br label %66, !dbg !254

66:                                               ; preds = %82, %65
  %67 = load i32, i32* %3, align 4, !dbg !255
  %68 = icmp slt i32 %67, 22, !dbg !257
  br i1 %68, label %69, label %85, !dbg !258

69:                                               ; preds = %66
  %70 = load i32, i32* %2, align 4, !dbg !259
  %71 = load i32, i32* %3, align 4, !dbg !261
  %72 = add nsw i32 %71, 2, !dbg !262
  %73 = mul nsw i32 %70, %72, !dbg !263
  %74 = sitofp i32 %73 to double, !dbg !264
  %75 = fdiv double %74, 2.200000e+01, !dbg !265
  %76 = load i32, i32* %2, align 4, !dbg !266
  %77 = sext i32 %76 to i64, !dbg !267
  %78 = getelementptr inbounds [18 x [22 x double]], [18 x [22 x double]]* @C, i64 0, i64 %77, !dbg !267
  %79 = load i32, i32* %3, align 4, !dbg !268
  %80 = sext i32 %79 to i64, !dbg !267
  %81 = getelementptr inbounds [22 x double], [22 x double]* %78, i64 0, i64 %80, !dbg !267
  store volatile double %75, double* %81, align 8, !dbg !269
  br label %82, !dbg !270

82:                                               ; preds = %69
  %83 = load i32, i32* %3, align 4, !dbg !271
  %84 = add nsw i32 %83, 1, !dbg !271
  store i32 %84, i32* %3, align 4, !dbg !271
  br label %66, !dbg !272, !llvm.loop !273

85:                                               ; preds = %66
  br label %86, !dbg !275

86:                                               ; preds = %85
  %87 = load i32, i32* %2, align 4, !dbg !276
  %88 = add nsw i32 %87, 1, !dbg !276
  store i32 %88, i32* %2, align 4, !dbg !276
  br label %62, !dbg !277, !llvm.loop !278

89:                                               ; preds = %62
  call void @kernel_2mm(double noundef 1.500000e+00, double noundef 1.200000e+00), !dbg !280
  call void @llvm.dbg.declare(metadata double* %4, metadata !281, metadata !DIExpression()), !dbg !282
  store double 0.000000e+00, double* %4, align 8, !dbg !282
  call void @llvm.dbg.declare(metadata i32* %5, metadata !283, metadata !DIExpression()), !dbg !285
  store i32 0, i32* %5, align 4, !dbg !285
  br label %90, !dbg !286

90:                                               ; preds = %111, %89
  %91 = load i32, i32* %5, align 4, !dbg !287
  %92 = icmp slt i32 %91, 16, !dbg !289
  br i1 %92, label %93, label %114, !dbg !290

93:                                               ; preds = %90
  call void @llvm.dbg.declare(metadata i32* %6, metadata !291, metadata !DIExpression()), !dbg !293
  store i32 0, i32* %6, align 4, !dbg !293
  br label %94, !dbg !294

94:                                               ; preds = %107, %93
  %95 = load i32, i32* %6, align 4, !dbg !295
  %96 = icmp slt i32 %95, 22, !dbg !297
  br i1 %96, label %97, label %110, !dbg !298

97:                                               ; preds = %94
  %98 = load i32, i32* %5, align 4, !dbg !299
  %99 = sext i32 %98 to i64, !dbg !300
  %100 = getelementptr inbounds [16 x [22 x double]], [16 x [22 x double]]* @D, i64 0, i64 %99, !dbg !300
  %101 = load i32, i32* %6, align 4, !dbg !301
  %102 = sext i32 %101 to i64, !dbg !300
  %103 = getelementptr inbounds [22 x double], [22 x double]* %100, i64 0, i64 %102, !dbg !300
  %104 = load volatile double, double* %103, align 8, !dbg !300
  %105 = load double, double* %4, align 8, !dbg !302
  %106 = fadd double %105, %104, !dbg !302
  store double %106, double* %4, align 8, !dbg !302
  br label %107, !dbg !303

107:                                              ; preds = %97
  %108 = load i32, i32* %6, align 4, !dbg !304
  %109 = add nsw i32 %108, 1, !dbg !304
  store i32 %109, i32* %6, align 4, !dbg !304
  br label %94, !dbg !305, !llvm.loop !306

110:                                              ; preds = %94
  br label %111, !dbg !307

111:                                              ; preds = %110
  %112 = load i32, i32* %5, align 4, !dbg !308
  %113 = add nsw i32 %112, 1, !dbg !308
  store i32 %113, i32* %5, align 4, !dbg !308
  br label %90, !dbg !309, !llvm.loop !310

114:                                              ; preds = %90
  %115 = load double, double* %4, align 8, !dbg !312
  %116 = call i32 (i8*, ...) @printf(i8* noundef getelementptr inbounds ([16 x i8], [16 x i8]* @.str.2, i64 0, i64 0), double noundef %115), !dbg !313
  ret i32 0, !dbg !314
}

declare i32 @printf(i8* noundef, ...) #2

attributes #0 = { noinline nounwind uwtable "frame-pointer"="all" "min-legal-vector-width"="0" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #1 = { nofree nosync nounwind readnone speculatable willreturn }
attributes #2 = { "frame-pointer"="all" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }

!llvm.dbg.cu = !{!2}
!llvm.module.flags = !{!31, !32, !33, !34, !35, !36, !37}
!llvm.ident = !{!38}

!0 = !DIGlobalVariableExpression(var: !1, expr: !DIExpression())
!1 = distinct !DIGlobalVariable(name: "tmp", scope: !2, file: !9, line: 24, type: !29, isLocal: false, isDefinition: true)
!2 = distinct !DICompileUnit(language: DW_LANG_C99, file: !3, producer: "Ubuntu clang version 14.0.0-1ubuntu1.1", isOptimized: false, runtimeVersion: 0, emissionKind: FullDebug, retainedTypes: !4, globals: !6, splitDebugInlining: false, nameTableKind: None)
!3 = !DIFile(filename: "/tmp/chaser-polybench-run-v1/2mm/workload.c", directory: "/tmp/chaser-polybench-run-v1/2mm", checksumkind: CSK_MD5, checksum: "22fcbece35a3a82290494ef54dd14e02")
!4 = !{!5}
!5 = !DIBasicType(name: "double", size: 64, encoding: DW_ATE_float)
!6 = !{!7, !15, !20, !25, !0}
!7 = !DIGlobalVariableExpression(var: !8, expr: !DIExpression())
!8 = distinct !DIGlobalVariable(name: "A", scope: !2, file: !9, line: 20, type: !10, isLocal: false, isDefinition: true)
!9 = !DIFile(filename: "workload.c", directory: "/tmp/chaser-polybench-run-v1/2mm", checksumkind: CSK_MD5, checksum: "22fcbece35a3a82290494ef54dd14e02")
!10 = !DICompositeType(tag: DW_TAG_array_type, baseType: !11, size: 20480, elements: !12)
!11 = !DIDerivedType(tag: DW_TAG_volatile_type, baseType: !5)
!12 = !{!13, !14}
!13 = !DISubrange(count: 16)
!14 = !DISubrange(count: 20)
!15 = !DIGlobalVariableExpression(var: !16, expr: !DIExpression())
!16 = distinct !DIGlobalVariable(name: "B", scope: !2, file: !9, line: 21, type: !17, isLocal: false, isDefinition: true)
!17 = !DICompositeType(tag: DW_TAG_array_type, baseType: !11, size: 23040, elements: !18)
!18 = !{!14, !19}
!19 = !DISubrange(count: 18)
!20 = !DIGlobalVariableExpression(var: !21, expr: !DIExpression())
!21 = distinct !DIGlobalVariable(name: "C", scope: !2, file: !9, line: 22, type: !22, isLocal: false, isDefinition: true)
!22 = !DICompositeType(tag: DW_TAG_array_type, baseType: !11, size: 25344, elements: !23)
!23 = !{!19, !24}
!24 = !DISubrange(count: 22)
!25 = !DIGlobalVariableExpression(var: !26, expr: !DIExpression())
!26 = distinct !DIGlobalVariable(name: "D", scope: !2, file: !9, line: 23, type: !27, isLocal: false, isDefinition: true)
!27 = !DICompositeType(tag: DW_TAG_array_type, baseType: !11, size: 22528, elements: !28)
!28 = !{!13, !24}
!29 = !DICompositeType(tag: DW_TAG_array_type, baseType: !11, size: 18432, elements: !30)
!30 = !{!13, !19}
!31 = !{i32 7, !"Dwarf Version", i32 5}
!32 = !{i32 2, !"Debug Info Version", i32 3}
!33 = !{i32 1, !"wchar_size", i32 4}
!34 = !{i32 7, !"PIC Level", i32 2}
!35 = !{i32 7, !"PIE Level", i32 2}
!36 = !{i32 7, !"uwtable", i32 1}
!37 = !{i32 7, !"frame-pointer", i32 2}
!38 = !{!"Ubuntu clang version 14.0.0-1ubuntu1.1"}
!39 = distinct !DISubprogram(name: "kernel_2mm", scope: !9, file: !9, line: 26, type: !40, scopeLine: 26, flags: DIFlagPrototyped, spFlags: DISPFlagDefinition, unit: !2, retainedNodes: !42)
!40 = !DISubroutineType(types: !41)
!41 = !{null, !5, !5}
!42 = !{}
!43 = !DILocalVariable(name: "alpha", arg: 1, scope: !39, file: !9, line: 26, type: !5)
!44 = !DILocation(line: 26, column: 74, scope: !39)
!45 = !DILocalVariable(name: "beta", arg: 2, scope: !39, file: !9, line: 26, type: !5)
!46 = !DILocation(line: 26, column: 88, scope: !39)
!47 = !DILocalVariable(name: "i", scope: !39, file: !9, line: 27, type: !48)
!48 = !DIBasicType(name: "int", size: 32, encoding: DW_ATE_signed)
!49 = !DILocation(line: 27, column: 9, scope: !39)
!50 = !DILocalVariable(name: "j", scope: !39, file: !9, line: 27, type: !48)
!51 = !DILocation(line: 27, column: 12, scope: !39)
!52 = !DILocalVariable(name: "k", scope: !39, file: !9, line: 27, type: !48)
!53 = !DILocation(line: 27, column: 15, scope: !39)
!54 = !DILocation(line: 30, column: 12, scope: !55)
!55 = distinct !DILexicalBlock(scope: !39, file: !9, line: 30, column: 5)
!56 = !DILocation(line: 30, column: 10, scope: !55)
!57 = !DILocation(line: 30, column: 17, scope: !58)
!58 = distinct !DILexicalBlock(scope: !55, file: !9, line: 30, column: 5)
!59 = !DILocation(line: 30, column: 19, scope: !58)
!60 = !DILocation(line: 30, column: 5, scope: !55)
!61 = !DILocation(line: 31, column: 16, scope: !62)
!62 = distinct !DILexicalBlock(scope: !63, file: !9, line: 31, column: 9)
!63 = distinct !DILexicalBlock(scope: !58, file: !9, line: 30, column: 30)
!64 = !DILocation(line: 31, column: 14, scope: !62)
!65 = !DILocation(line: 31, column: 21, scope: !66)
!66 = distinct !DILexicalBlock(scope: !62, file: !9, line: 31, column: 9)
!67 = !DILocation(line: 31, column: 23, scope: !66)
!68 = !DILocation(line: 31, column: 9, scope: !62)
!69 = !DILocation(line: 32, column: 17, scope: !70)
!70 = distinct !DILexicalBlock(scope: !66, file: !9, line: 31, column: 34)
!71 = !DILocation(line: 32, column: 13, scope: !70)
!72 = !DILocation(line: 32, column: 20, scope: !70)
!73 = !DILocation(line: 32, column: 23, scope: !70)
!74 = !DILocation(line: 33, column: 20, scope: !75)
!75 = distinct !DILexicalBlock(scope: !70, file: !9, line: 33, column: 13)
!76 = !DILocation(line: 33, column: 18, scope: !75)
!77 = !DILocation(line: 33, column: 25, scope: !78)
!78 = distinct !DILexicalBlock(scope: !75, file: !9, line: 33, column: 13)
!79 = !DILocation(line: 33, column: 27, scope: !78)
!80 = !DILocation(line: 33, column: 13, scope: !75)
!81 = !DILocation(line: 34, column: 30, scope: !82)
!82 = distinct !DILexicalBlock(scope: !78, file: !9, line: 33, column: 38)
!83 = !DILocation(line: 34, column: 40, scope: !82)
!84 = !DILocation(line: 34, column: 38, scope: !82)
!85 = !DILocation(line: 34, column: 43, scope: !82)
!86 = !DILocation(line: 34, column: 36, scope: !82)
!87 = !DILocation(line: 34, column: 50, scope: !82)
!88 = !DILocation(line: 34, column: 48, scope: !82)
!89 = !DILocation(line: 34, column: 53, scope: !82)
!90 = !DILocation(line: 34, column: 21, scope: !82)
!91 = !DILocation(line: 34, column: 17, scope: !82)
!92 = !DILocation(line: 34, column: 24, scope: !82)
!93 = !DILocation(line: 34, column: 27, scope: !82)
!94 = !DILocation(line: 36, column: 13, scope: !82)
!95 = !DILocation(line: 33, column: 34, scope: !78)
!96 = !DILocation(line: 33, column: 13, scope: !78)
!97 = distinct !{!97, !80, !98, !99}
!98 = !DILocation(line: 36, column: 13, scope: !75)
!99 = !{!"llvm.loop.mustprogress"}
!100 = !DILocation(line: 37, column: 9, scope: !70)
!101 = !DILocation(line: 31, column: 30, scope: !66)
!102 = !DILocation(line: 31, column: 9, scope: !66)
!103 = distinct !{!103, !68, !104, !99}
!104 = !DILocation(line: 37, column: 9, scope: !62)
!105 = !DILocation(line: 38, column: 5, scope: !63)
!106 = !DILocation(line: 30, column: 26, scope: !58)
!107 = !DILocation(line: 30, column: 5, scope: !58)
!108 = distinct !{!108, !60, !109, !99}
!109 = !DILocation(line: 38, column: 5, scope: !55)
!110 = !DILocation(line: 41, column: 12, scope: !111)
!111 = distinct !DILexicalBlock(scope: !39, file: !9, line: 41, column: 5)
!112 = !DILocation(line: 41, column: 10, scope: !111)
!113 = !DILocation(line: 41, column: 17, scope: !114)
!114 = distinct !DILexicalBlock(scope: !111, file: !9, line: 41, column: 5)
!115 = !DILocation(line: 41, column: 19, scope: !114)
!116 = !DILocation(line: 41, column: 5, scope: !111)
!117 = !DILocation(line: 42, column: 16, scope: !118)
!118 = distinct !DILexicalBlock(scope: !119, file: !9, line: 42, column: 9)
!119 = distinct !DILexicalBlock(scope: !114, file: !9, line: 41, column: 30)
!120 = !DILocation(line: 42, column: 14, scope: !118)
!121 = !DILocation(line: 42, column: 21, scope: !122)
!122 = distinct !DILexicalBlock(scope: !118, file: !9, line: 42, column: 9)
!123 = !DILocation(line: 42, column: 23, scope: !122)
!124 = !DILocation(line: 42, column: 9, scope: !118)
!125 = !DILocation(line: 43, column: 15, scope: !126)
!126 = distinct !DILexicalBlock(scope: !122, file: !9, line: 42, column: 34)
!127 = !DILocation(line: 43, column: 13, scope: !126)
!128 = !DILocation(line: 43, column: 18, scope: !126)
!129 = !DILocation(line: 43, column: 21, scope: !126)
!130 = !DILocation(line: 44, column: 20, scope: !131)
!131 = distinct !DILexicalBlock(scope: !126, file: !9, line: 44, column: 13)
!132 = !DILocation(line: 44, column: 18, scope: !131)
!133 = !DILocation(line: 44, column: 25, scope: !134)
!134 = distinct !DILexicalBlock(scope: !131, file: !9, line: 44, column: 13)
!135 = !DILocation(line: 44, column: 27, scope: !134)
!136 = !DILocation(line: 44, column: 13, scope: !131)
!137 = !DILocation(line: 45, column: 28, scope: !138)
!138 = distinct !DILexicalBlock(scope: !134, file: !9, line: 44, column: 38)
!139 = !DILocation(line: 45, column: 39, scope: !138)
!140 = !DILocation(line: 45, column: 35, scope: !138)
!141 = !DILocation(line: 45, column: 42, scope: !138)
!142 = !DILocation(line: 45, column: 33, scope: !138)
!143 = !DILocation(line: 45, column: 49, scope: !138)
!144 = !DILocation(line: 45, column: 47, scope: !138)
!145 = !DILocation(line: 45, column: 52, scope: !138)
!146 = !DILocation(line: 45, column: 19, scope: !138)
!147 = !DILocation(line: 45, column: 17, scope: !138)
!148 = !DILocation(line: 45, column: 22, scope: !138)
!149 = !DILocation(line: 45, column: 25, scope: !138)
!150 = !DILocation(line: 47, column: 13, scope: !138)
!151 = !DILocation(line: 44, column: 34, scope: !134)
!152 = !DILocation(line: 44, column: 13, scope: !134)
!153 = distinct !{!153, !136, !154, !99}
!154 = !DILocation(line: 47, column: 13, scope: !131)
!155 = !DILocation(line: 48, column: 9, scope: !126)
!156 = !DILocation(line: 42, column: 30, scope: !122)
!157 = !DILocation(line: 42, column: 9, scope: !122)
!158 = distinct !{!158, !124, !159, !99}
!159 = !DILocation(line: 48, column: 9, scope: !118)
!160 = !DILocation(line: 49, column: 5, scope: !119)
!161 = !DILocation(line: 41, column: 26, scope: !114)
!162 = !DILocation(line: 41, column: 5, scope: !114)
!163 = distinct !{!163, !116, !164, !99}
!164 = !DILocation(line: 49, column: 5, scope: !111)
!165 = !DILocation(line: 50, column: 1, scope: !39)
!166 = distinct !DISubprogram(name: "main", scope: !9, file: !9, line: 52, type: !167, scopeLine: 52, spFlags: DISPFlagDefinition, unit: !2, retainedNodes: !42)
!167 = !DISubroutineType(types: !168)
!168 = !{!48}
!169 = !DILocalVariable(name: "i", scope: !166, file: !9, line: 53, type: !48)
!170 = !DILocation(line: 53, column: 9, scope: !166)
!171 = !DILocalVariable(name: "j", scope: !166, file: !9, line: 53, type: !48)
!172 = !DILocation(line: 53, column: 12, scope: !166)
!173 = !DILocation(line: 56, column: 12, scope: !174)
!174 = distinct !DILexicalBlock(scope: !166, file: !9, line: 56, column: 5)
!175 = !DILocation(line: 56, column: 10, scope: !174)
!176 = !DILocation(line: 56, column: 17, scope: !177)
!177 = distinct !DILexicalBlock(scope: !174, file: !9, line: 56, column: 5)
!178 = !DILocation(line: 56, column: 19, scope: !177)
!179 = !DILocation(line: 56, column: 5, scope: !174)
!180 = !DILocation(line: 57, column: 16, scope: !181)
!181 = distinct !DILexicalBlock(scope: !182, file: !9, line: 57, column: 9)
!182 = distinct !DILexicalBlock(scope: !177, file: !9, line: 56, column: 30)
!183 = !DILocation(line: 57, column: 14, scope: !181)
!184 = !DILocation(line: 57, column: 21, scope: !185)
!185 = distinct !DILexicalBlock(scope: !181, file: !9, line: 57, column: 9)
!186 = !DILocation(line: 57, column: 23, scope: !185)
!187 = !DILocation(line: 57, column: 9, scope: !181)
!188 = !DILocation(line: 58, column: 32, scope: !189)
!189 = distinct !DILexicalBlock(scope: !185, file: !9, line: 57, column: 34)
!190 = !DILocation(line: 58, column: 36, scope: !189)
!191 = !DILocation(line: 58, column: 34, scope: !189)
!192 = !DILocation(line: 58, column: 23, scope: !189)
!193 = !DILocation(line: 58, column: 39, scope: !189)
!194 = !DILocation(line: 58, column: 15, scope: !189)
!195 = !DILocation(line: 58, column: 13, scope: !189)
!196 = !DILocation(line: 58, column: 18, scope: !189)
!197 = !DILocation(line: 58, column: 21, scope: !189)
!198 = !DILocation(line: 59, column: 9, scope: !189)
!199 = !DILocation(line: 57, column: 30, scope: !185)
!200 = !DILocation(line: 57, column: 9, scope: !185)
!201 = distinct !{!201, !187, !202, !99}
!202 = !DILocation(line: 59, column: 9, scope: !181)
!203 = !DILocation(line: 60, column: 5, scope: !182)
!204 = !DILocation(line: 56, column: 26, scope: !177)
!205 = !DILocation(line: 56, column: 5, scope: !177)
!206 = distinct !{!206, !179, !207, !99}
!207 = !DILocation(line: 60, column: 5, scope: !174)
!208 = !DILocation(line: 62, column: 12, scope: !209)
!209 = distinct !DILexicalBlock(scope: !166, file: !9, line: 62, column: 5)
!210 = !DILocation(line: 62, column: 10, scope: !209)
!211 = !DILocation(line: 62, column: 17, scope: !212)
!212 = distinct !DILexicalBlock(scope: !209, file: !9, line: 62, column: 5)
!213 = !DILocation(line: 62, column: 19, scope: !212)
!214 = !DILocation(line: 62, column: 5, scope: !209)
!215 = !DILocation(line: 63, column: 16, scope: !216)
!216 = distinct !DILexicalBlock(scope: !217, file: !9, line: 63, column: 9)
!217 = distinct !DILexicalBlock(scope: !212, file: !9, line: 62, column: 30)
!218 = !DILocation(line: 63, column: 14, scope: !216)
!219 = !DILocation(line: 63, column: 21, scope: !220)
!220 = distinct !DILexicalBlock(scope: !216, file: !9, line: 63, column: 9)
!221 = !DILocation(line: 63, column: 23, scope: !220)
!222 = !DILocation(line: 63, column: 9, scope: !216)
!223 = !DILocation(line: 64, column: 32, scope: !224)
!224 = distinct !DILexicalBlock(scope: !220, file: !9, line: 63, column: 34)
!225 = !DILocation(line: 64, column: 37, scope: !224)
!226 = !DILocation(line: 64, column: 39, scope: !224)
!227 = !DILocation(line: 64, column: 34, scope: !224)
!228 = !DILocation(line: 64, column: 23, scope: !224)
!229 = !DILocation(line: 64, column: 45, scope: !224)
!230 = !DILocation(line: 64, column: 15, scope: !224)
!231 = !DILocation(line: 64, column: 13, scope: !224)
!232 = !DILocation(line: 64, column: 18, scope: !224)
!233 = !DILocation(line: 64, column: 21, scope: !224)
!234 = !DILocation(line: 65, column: 9, scope: !224)
!235 = !DILocation(line: 63, column: 30, scope: !220)
!236 = !DILocation(line: 63, column: 9, scope: !220)
!237 = distinct !{!237, !222, !238, !99}
!238 = !DILocation(line: 65, column: 9, scope: !216)
!239 = !DILocation(line: 66, column: 5, scope: !217)
!240 = !DILocation(line: 62, column: 26, scope: !212)
!241 = !DILocation(line: 62, column: 5, scope: !212)
!242 = distinct !{!242, !214, !243, !99}
!243 = !DILocation(line: 66, column: 5, scope: !209)
!244 = !DILocation(line: 68, column: 12, scope: !245)
!245 = distinct !DILexicalBlock(scope: !166, file: !9, line: 68, column: 5)
!246 = !DILocation(line: 68, column: 10, scope: !245)
!247 = !DILocation(line: 68, column: 17, scope: !248)
!248 = distinct !DILexicalBlock(scope: !245, file: !9, line: 68, column: 5)
!249 = !DILocation(line: 68, column: 19, scope: !248)
!250 = !DILocation(line: 68, column: 5, scope: !245)
!251 = !DILocation(line: 69, column: 16, scope: !252)
!252 = distinct !DILexicalBlock(scope: !253, file: !9, line: 69, column: 9)
!253 = distinct !DILexicalBlock(scope: !248, file: !9, line: 68, column: 30)
!254 = !DILocation(line: 69, column: 14, scope: !252)
!255 = !DILocation(line: 69, column: 21, scope: !256)
!256 = distinct !DILexicalBlock(scope: !252, file: !9, line: 69, column: 9)
!257 = !DILocation(line: 69, column: 23, scope: !256)
!258 = !DILocation(line: 69, column: 9, scope: !252)
!259 = !DILocation(line: 70, column: 32, scope: !260)
!260 = distinct !DILexicalBlock(scope: !256, file: !9, line: 69, column: 34)
!261 = !DILocation(line: 70, column: 37, scope: !260)
!262 = !DILocation(line: 70, column: 39, scope: !260)
!263 = !DILocation(line: 70, column: 34, scope: !260)
!264 = !DILocation(line: 70, column: 23, scope: !260)
!265 = !DILocation(line: 70, column: 45, scope: !260)
!266 = !DILocation(line: 70, column: 15, scope: !260)
!267 = !DILocation(line: 70, column: 13, scope: !260)
!268 = !DILocation(line: 70, column: 18, scope: !260)
!269 = !DILocation(line: 70, column: 21, scope: !260)
!270 = !DILocation(line: 71, column: 9, scope: !260)
!271 = !DILocation(line: 69, column: 30, scope: !256)
!272 = !DILocation(line: 69, column: 9, scope: !256)
!273 = distinct !{!273, !258, !274, !99}
!274 = !DILocation(line: 71, column: 9, scope: !252)
!275 = !DILocation(line: 72, column: 5, scope: !253)
!276 = !DILocation(line: 68, column: 26, scope: !248)
!277 = !DILocation(line: 68, column: 5, scope: !248)
!278 = distinct !{!278, !250, !279, !99}
!279 = !DILocation(line: 72, column: 5, scope: !245)
!280 = !DILocation(line: 74, column: 5, scope: !166)
!281 = !DILocalVariable(name: "checksum", scope: !166, file: !9, line: 76, type: !5)
!282 = !DILocation(line: 76, column: 12, scope: !166)
!283 = !DILocalVariable(name: "ci", scope: !284, file: !9, line: 77, type: !48)
!284 = distinct !DILexicalBlock(scope: !166, file: !9, line: 77, column: 5)
!285 = !DILocation(line: 77, column: 14, scope: !284)
!286 = !DILocation(line: 77, column: 10, scope: !284)
!287 = !DILocation(line: 77, column: 19, scope: !288)
!288 = distinct !DILexicalBlock(scope: !284, file: !9, line: 77, column: 5)
!289 = !DILocation(line: 77, column: 21, scope: !288)
!290 = !DILocation(line: 77, column: 5, scope: !284)
!291 = !DILocalVariable(name: "cj", scope: !292, file: !9, line: 77, type: !48)
!292 = distinct !DILexicalBlock(scope: !288, file: !9, line: 77, column: 31)
!293 = !DILocation(line: 77, column: 40, scope: !292)
!294 = !DILocation(line: 77, column: 36, scope: !292)
!295 = !DILocation(line: 77, column: 45, scope: !296)
!296 = distinct !DILexicalBlock(scope: !292, file: !9, line: 77, column: 31)
!297 = !DILocation(line: 77, column: 47, scope: !296)
!298 = !DILocation(line: 77, column: 31, scope: !292)
!299 = !DILocation(line: 77, column: 71, scope: !296)
!300 = !DILocation(line: 77, column: 69, scope: !296)
!301 = !DILocation(line: 77, column: 75, scope: !296)
!302 = !DILocation(line: 77, column: 66, scope: !296)
!303 = !DILocation(line: 77, column: 57, scope: !296)
!304 = !DILocation(line: 77, column: 53, scope: !296)
!305 = !DILocation(line: 77, column: 31, scope: !296)
!306 = distinct !{!306, !298, !307, !99}
!307 = !DILocation(line: 77, column: 77, scope: !292)
!308 = !DILocation(line: 77, column: 27, scope: !288)
!309 = !DILocation(line: 77, column: 5, scope: !288)
!310 = distinct !{!310, !290, !311, !99}
!311 = !DILocation(line: 77, column: 77, scope: !284)
!312 = !DILocation(line: 78, column: 32, scope: !166)
!313 = !DILocation(line: 78, column: 5, scope: !166)
!314 = !DILocation(line: 79, column: 5, scope: !166)
